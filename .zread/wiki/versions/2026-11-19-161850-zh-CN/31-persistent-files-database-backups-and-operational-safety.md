本页说明应用将持久状态保存在何处、如何通过文件写入降低部分写入的风险，以及当前部署配置对备份和恢复提供了什么、又没有提供什么。关键的运维区别在于 **业务数据**、**工作流检查点**和**上传或生成的文件**：它们位于不同路径，必须分别保护。来源：[docker-compose.yml](docker-compose.yml#L10-L24)、[database.py](backend/app/database.py#L1-L5)、[checkpointer.py](backend/app/workflow/checkpointer.py#L1-L5)、[file_storage.py](backend/app/services/file_storage.py#L1-L10)

## 持久状态映射

后端使用三类持久状态。在 Compose 中，业务数据库和文件存储从主机挂载；检查点数据库由应用代码单独存储，**不**包含在 Compose 卷列表中。SQLite 的 WAL 模式还可能在数据库使用期间创建配套的 `-wal` 和 `-shm` 文件。来源：[docker-compose.yml](docker-compose.yml#L10-L24)、[database.py](backend/app/database.py#L24-L44)、[checkpointer.py](backend/app/workflow/checkpointer.py#L20-L49)

| 状态类别 | 默认或配置的位置 | 持久性和运维意义 |
|---|---|---|
| 业务数据库 | 主机上的 `backend/interview.db`，挂载到 `/app/interview.db`；在 Compose 中配置为 `sqlite:///./interview.db` | 存储应用业务数据。SQLite 使用 WAL 模式、启用外键，并设置 5 秒的忙碌超时。 |
| 工作流检查点 | `backend/workflow_checkpoints.db` | LangGraph 的 `SqliteSaver` 使用的独立 SQLite 数据库。未在 `docker-compose.yml` 中显式挂载。 |
| 上传和生成的文件 | 主机上的 `backend/storage/`，挂载到 `/app/storage` | 在配置的存储根目录下存放简历、音频、报告和日志。 |
| SQLite WAL 辅助文件 | 使用期间位于相应 SQLite 数据库文件旁 | SQLite 运行时文件；`.db-wal` 和 `.db-shm` 条目会被 Git 忽略。 |

来源：[docker-compose.yml](docker-compose.yml#L14-L24)、[database.py](backend/app/database.py#L24-L44)、[checkpointer.py](backend/app/workflow/checkpointer.py#L20-L49)、[.gitignore](.gitignore#L28-L43)、[main.py](backend/app/main.py#L67-L71)

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

    DB -->|Compose 绑定挂载| ADB
    ST -->|Compose 绑定挂载| AST
    ACP -.->|未显示显式 Compose 挂载| CP
```

此图区分了两个已配置的主机绑定挂载与由应用解析出的检查点路径。检查点模块根据后端包的位置推导路径，而 Compose 只将存储目录和业务数据库列为 API 卷。来源：[docker-compose.yml](docker-compose.yml#L10-L24)、[checkpointer.py](backend/app/workflow/checkpointer.py#L20-L49)

## 文件存储行为和持久性边界

`LocalFileStorage` 按类别组织文件：简历使用 `resumes/{candidate_id}/original.{ext}`，面试音频使用 `audio/{interview_id}/{question_id}.webm`，报告使用 `reports/{interview_id}.pdf`。根目录来自 `STORAGE_PATH`；在 Compose 服务中，该值为 `/app/storage`，并绑定挂载到 `./backend/storage`。应用启动时会创建存储根目录以及 `resumes`、`audio`、`reports` 和 `logs` 目录。来源：[file_storage.py](backend/app/services/file_storage.py#L43-L62)、[file_storage.py](backend/app/services/file_storage.py#L92-L113)、[config.py](backend/app/config.py#L31-L35)、[docker-compose.yml](docker-compose.yml#L14-L24)、[main.py](backend/app/main.py#L67-L71)

保存文件时，会创建父目录，写入同级的 `.tmp` 文件，刷新并调用 `fsync`，然后通过 `os.replace` 替换目标文件。发生异常时，代码会尝试删除临时文件，然后重新抛出异常。这降低了读取者看到部分写入目标文件的风险，但这不是备份机制：它不会保留旧版本、复制数据，也不会与数据库更改协调事务。来源：[file_storage.py](backend/app/services/file_storage.py#L64-L90)

## 数据库分离和备份影响

业务数据库引擎根据 `DATABASE_URL` 配置。对于 SQLite，它会禁用默认的同线程限制，在连接时启用 WAL 模式和外键，并设置 `busy_timeout=5000`。这些设置支持应用的 SQLite 访问模式；它们并未建立备份计划，也不能保证在主机或卷丢失时恢复数据。来源：[database.py](backend/app/database.py#L24-L44)

工作流检查点存储在物理上与业务数据库分离，并通过 `SqliteSaver` 打开。模块注释将 SQLite 描述为 MVP 实现，并提到 PostgreSQL 是未来可用于生产环境的替代方案；已提交的 Compose 配置并未提供此类服务。在运维上，仅保留 `interview.db` 并不能保留工作流检查点；仅保留检查点数据库也不能保留业务记录或存储的文件。来源：[checkpointer.py](backend/app/workflow/checkpointer.py#L1-L5)、[checkpointer.py](backend/app/workflow/checkpointer.py#L20-L49)、[docker-compose.yml](docker-compose.yml#L10-L24)

仓库包含一个 `db_backup_20261119_143926/interview.db` 目录和文件，但经检查的应用和 Compose 配置并未定义备份命令、轮换策略、保留期限或恢复流程。应将该文件视为仓库中的文件，而非自动备份系统的证据。来源：[database.py](backend/app/database.py#L1-L5)、[docker-compose.yml](docker-compose.yml#L10-L24)

## 仓库跟踪和容器持久性

`.gitignore` 规则会忽略 SQLite WAL/SHM 辅助文件以及 `backend/storage` 下的运行时内容，同时明确允许 `backend/storage/.gitkeep`。通用的 `*.db` 忽略规则已被注释，因此它本身不会排除数据库文件；`workflow_checkpoints.db` 则被明确忽略。因此，Git 忽略规则不能替代运维备份策略；开发者在提交更改前应确认实际跟踪了哪些数据库文件。来源：[.gitignore](.gitignore#L28-L43)

Compose 将 `./backend/storage` 和 `./backend/interview.db` 绑定挂载到 API 容器，因此这些路径与主机文件关联。检查点数据库没有对应的挂载声明。Dockerfile 将应用源代码复制到 `/app`，以非 root 用户 `appuser` 身份运行，且未声明 Docker 卷；因此，除非添加外部挂载，否则检查点持久性取决于容器的可写文件系统。即使两个已配置的绑定挂载路径仍保留在主机上，重新创建容器仍可能影响检查点的持久性。来源：[docker-compose.yml](docker-compose.yml#L10-L24)、[Dockerfile](backend/Dockerfile#L49-L76)、[checkpointer.py](backend/app/workflow/checkpointer.py#L20-L49)

## 运维安全检查清单

| 运维关注点 | 已验证的实现 | 安全边界 |
|---|---|---|
| 文件替换 | 临时同级文件、刷新、`fsync`，然后调用 `os.replace` | 保护目标文件，避免被部分写入的文件替换；不提供历史版本。 |
| 业务 SQLite 配置 | WAL、外键、5 秒忙碌超时 | 数据库并发设置，而非备份或时间点恢复策略。 |
| Compose 中业务数据库的持久性 | 为 `./backend/interview.db` 配置主机绑定挂载 | 可应对常规容器替换，但无法防止主机文件丢失或损坏。 |
| Compose 中存储的持久性 | 为 `./backend/storage` 配置主机绑定挂载 | 将存储文件保存在容器可写层之外；主机级保护仍需另行提供。 |
| Compose 中检查点的持久性 | 检查点文件路径在应用代码中定义；Compose 未显式挂载 | 不要假定检查点文件在容器重新创建后仍然存在。 |
| 启动时创建目录 | 应用会创建存储根目录和类别目录 | 创建目录并不能验证备份完整性或恢复就绪情况。 |

来源：[file_storage.py](backend/app/services/file_storage.py#L64-L90)、[database.py](backend/app/database.py#L24-L44)、[docker-compose.yml](docker-compose.yml#L10-L24)、[checkpointer.py](backend/app/workflow/checkpointer.py#L20-L49)、[main.py](backend/app/main.py#L67-L71)

设计运维备份方案时，应清点并保护全部三类数据——业务数据库、工作流检查点和存储文件——并针对正在运行的应用版本验证恢复过程。仓库证据说明了这些数据的位置及当前的持久化配置，但没有规定安全的 SQLite 在线备份流程、调度机制、保留策略、异地主机副本或经过测试的恢复工作流；这些内容应由部署运维流程提供，而不应从代码中推断。来源：[docker-compose.yml](docker-compose.yml#L10-L24)、[database.py](backend/app/database.py#L24-L44)、[checkpointer.py](backend/app/workflow/checkpointer.py#L20-L49)、[file_storage.py](backend/app/services/file_storage.py#L43-L90)

## 延伸阅读

如需了解更广泛的部署拓扑和反向代理行为，请继续阅读[Docker Compose、Nginx 和支持 SSE 的部署](30-docker-compose-nginx-and-sse-aware-deployment)。如需了解应用层的 SQLite WAL 配置，以及业务数据与工作流检查点之间的分离，请参阅[SQLite WAL、业务数据和工作流检查点](18-sqlite-wal-business-data-and-workflow-checkpoints)。来源：[docker-compose.yml](docker-compose.yml#L1-L10)、[database.py](backend/app/database.py#L1-L5)、[checkpointer.py](backend/app/workflow/checkpointer.py#L1-L5)
