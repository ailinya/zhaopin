This page explains where the application keeps durable state, how file writes are made safer against partial output, and what the current deployment configuration does—and does not—provide for backup and recovery. The key operational distinction is between **business data**, **workflow checkpoints**, and **uploaded or generated files**: they occupy separate paths and must be protected independently. Sources: [docker-compose.yml](docker-compose.yml#L10-L24), [database.py](backend/app/database.py#L1-L5), [checkpointer.py](backend/app/workflow/checkpointer.py#L1-L5), [file_storage.py](backend/app/services/file_storage.py#L1-L10)

## Persistent-state map

The backend uses three persistent-state categories. In Compose, the business database and file storage are mounted from the host; the checkpoint database is stored separately by the application code and is **not** included in the Compose volume list. SQLite’s WAL mode can also create companion `-wal` and `-shm` files while the database is in use. Sources: [docker-compose.yml](docker-compose.yml#L10-L24), [database.py](backend/app/database.py#L24-L44), [checkpointer.py](backend/app/workflow/checkpointer.py#L20-L49)

| State category | Default or configured location | Persistence and operational significance |
|---|---|---|
| Business database | `backend/interview.db` on the host, mounted at `/app/interview.db`; configured in Compose as `sqlite:///./interview.db` | Stores application business data. SQLite uses WAL mode, enables foreign keys, and sets a 5-second busy timeout. |
| Workflow checkpoints | `backend/workflow_checkpoints.db` | A separate SQLite database used by LangGraph’s `SqliteSaver`. It is not mounted explicitly in `docker-compose.yml`. |
| Uploaded and generated files | `backend/storage/` on the host, mounted at `/app/storage` | Holds resumes, audio, reports, and logs under the configured storage root. |
| SQLite WAL sidecars | Adjacent to the relevant SQLite database file while in use | Runtime SQLite files; `.db-wal` and `.db-shm` entries are ignored by Git. |

Sources: [docker-compose.yml](docker-compose.yml#L14-L24), [database.py](backend/app/database.py#L24-L44), [checkpointer.py](backend/app/workflow/checkpointer.py#L20-L49), [.gitignore](.gitignore#L28-L43), [main.py](backend/app/main.py#L67-L71)

```mermaid
flowchart LR
    subgraph Host
        DB[backend/interview.db]
        ST[backend/storage/]
        CP[backend/workflow_checkpoints.db]
    end

    subgraph API container
        ADB[/app/interview.db]
        AST[/app/storage/]
        ACP[/app/app/workflow_checkpoints.db]
    end

    DB -->|Compose bind mount| ADB
    ST -->|Compose bind mount| AST
    ACP -.->|No explicit Compose mount shown| CP
```

This diagram distinguishes the two configured host bind mounts from the checkpoint path resolved by the application. The checkpoint module derives its path from the backend package location, whereas Compose lists only the storage directory and business database as API volumes. Sources: [docker-compose.yml](docker-compose.yml#L10-L24), [checkpointer.py](backend/app/workflow/checkpointer.py#L20-L49)

## File-storage behavior and durability boundaries

`LocalFileStorage` organizes files by category: resumes use `resumes/{candidate_id}/original.{ext}`, interview audio uses `audio/{interview_id}/{question_id}.webm`, and reports use `reports/{interview_id}.pdf`. The root comes from `STORAGE_PATH`; in the Compose service this is `/app/storage`, which is bind-mounted to `./backend/storage`. At startup, the application creates the storage root and the `resumes`, `audio`, `reports`, and `logs` directories. Sources: [file_storage.py](backend/app/services/file_storage.py#L43-L62), [file_storage.py](backend/app/services/file_storage.py#L92-L113), [config.py](backend/app/config.py#L31-L35), [docker-compose.yml](docker-compose.yml#L14-L24), [main.py](backend/app/main.py#L67-L71)

Saving a file creates the parent directory, writes to a sibling `.tmp` file, flushes and calls `fsync`, then replaces the target with `os.replace`. On exceptions, it attempts to remove the temporary file before re-raising. This reduces the risk of readers seeing a partially written target, but it is not a backup mechanism: it does not preserve older versions, replicate data, or coordinate a transaction with database changes. Sources: [file_storage.py](backend/app/services/file_storage.py#L64-L90)

## Database separation and backup implications

The business database engine is configured from `DATABASE_URL`. For SQLite, it disables the default same-thread restriction, enables WAL mode and foreign keys on connection, and sets `busy_timeout=5000`. These settings support the application’s SQLite access pattern; they do not establish a backup schedule or guarantee recovery from host or volume loss. Sources: [database.py](backend/app/database.py#L24-L44)

The workflow checkpoint store is physically separate from the business database and is opened through `SqliteSaver`. The module’s comments describe SQLite as the MVP implementation and mention PostgreSQL as a future production alternative; the checked-in Compose configuration does not provide such a service. Operationally, preserving only `interview.db` does not preserve workflow checkpoints, and preserving only the checkpoint database does not preserve business records or stored files. Sources: [checkpointer.py](backend/app/workflow/checkpointer.py#L1-L5), [checkpointer.py](backend/app/workflow/checkpointer.py#L20-L49), [docker-compose.yml](docker-compose.yml#L10-L24)

The repository includes a `db_backup_20261119_143926/interview.db` directory and file, but the inspected application and Compose configuration do not define a backup command, rotation policy, retention period, or restore procedure. Treat the presence of that file as a repository artifact, not evidence of an automated backup system. Sources: [database.py](backend/app/database.py#L1-L5), [docker-compose.yml](docker-compose.yml#L10-L24)

## Repository tracking and container persistence

The `.gitignore` rules ignore SQLite WAL/SHM sidecars and runtime contents beneath `backend/storage`, while explicitly allowing `backend/storage/.gitkeep`. The general `*.db` ignore rule is commented out, so it does not exclude database files by itself; `workflow_checkpoints.db` is explicitly ignored. Consequently, Git ignore rules are not a substitute for an operational backup policy, and developers should verify which database artifacts are actually tracked before committing changes. Sources: [.gitignore](.gitignore#L28-L43)

Compose bind-mounts `./backend/storage` and `./backend/interview.db` into the API container, so those paths are tied to host files. No corresponding mount is declared for the checkpoint database. The Dockerfile copies application source into `/app`, runs as the non-root `appuser`, and declares no Docker volume; therefore, checkpoint persistence depends on the container’s writable filesystem unless an external mount is added. Recreating the container can therefore affect checkpoint durability even when the two configured bind-mounted paths remain on the host. Sources: [docker-compose.yml](docker-compose.yml#L10-L24), [Dockerfile](backend/Dockerfile#L49-L76), [checkpointer.py](backend/app/workflow/checkpointer.py#L20-L49)

## Operational safety checklist

| Operational concern | Verified implementation | Safety boundary |
|---|---|---|
| File replacement | Temporary sibling file, flush, `fsync`, then `os.replace` | Protects the target from a partially written replacement; does not provide historical versions. |
| Business SQLite configuration | WAL, foreign keys, 5-second busy timeout | Database concurrency settings, not a backup or point-in-time recovery policy. |
| Business DB persistence in Compose | Host bind mount for `./backend/interview.db` | Protects against ordinary container replacement, but not loss or corruption of the host file. |
| Storage persistence in Compose | Host bind mount for `./backend/storage` | Keeps stored files outside the container writable layer; host-level protection remains external. |
| Checkpoint persistence in Compose | Checkpoint file path is defined in application code; no explicit Compose mount | Do not assume the checkpoint file survives container recreation. |
| Startup directories | Application creates storage root and category directories | Directory creation does not validate backup integrity or restore readiness. |

Sources: [file_storage.py](backend/app/services/file_storage.py#L64-L90), [database.py](backend/app/database.py#L24-L44), [docker-compose.yml](docker-compose.yml#L10-L24), [checkpointer.py](backend/app/workflow/checkpointer.py#L20-L49), [main.py](backend/app/main.py#L67-L71)

For an operational backup design, inventory and protect all three categories—business database, workflow checkpoints, and storage files—and validate restoration against the version of the application being operated. The repository evidence establishes their locations and current persistence wiring, but does not specify a safe live-SQLite backup procedure, scheduling mechanism, retention policy, off-host copy, or tested restore workflow; those need to be supplied by the deployment’s operational procedures rather than inferred from this code. Sources: [docker-compose.yml](docker-compose.yml#L10-L24), [database.py](backend/app/database.py#L24-L44), [checkpointer.py](backend/app/workflow/checkpointer.py#L20-L49), [file_storage.py](backend/app/services/file_storage.py#L43-L90)

## Related reading

For broader deployment topology and reverse-proxy behavior, continue with [Docker Compose, Nginx, and SSE-Aware Deployment](30-docker-compose-nginx-and-sse-aware-deployment). For SQLite’s application-level WAL configuration and the separation between business data and workflow checkpoints, see [SQLite WAL, Business Data, and Workflow Checkpoints](18-sqlite-wal-business-data-and-workflow-checkpoints). Sources: [docker-compose.yml](docker-compose.yml#L1-L10), [database.py](backend/app/database.py#L1-L5), [checkpointer.py](backend/app/workflow/checkpointer.py#L1-L5)