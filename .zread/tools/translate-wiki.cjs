const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');

const root = path.resolve('.zread/wiki');
const sourceId = '2026-11-19-161850';
const targetId = `${sourceId}-zh-CN`;
const sourceDir = path.join(root, 'versions', sourceId);
const targetDir = path.join(root, 'versions', targetId);
const titles = [
  '项目概览', '快速开始', '招聘工作流程与用户角色', '代码库结构与推荐阅读路径',
  '本地配置与环境变量', '系统架构与组件边界', '招聘领域模型与数据关系',
  'API 契约、数据校验与错误处理', '身份认证、权限控制与候选人访问',
  '面试工作流状态与生命周期', 'LangGraph 节点、中断与恢复语义',
  '工作流依赖注入与检查点持久化', '大模型提供方、提示词模板与结构化输出',
  '简历解析与候选人数据准备', '语音录制、FFmpeg 与 Whisper 转写',
  '评估报告与 PDF 渲染', '服务层、仓储与数据库会话',
  'SQLite WAL、业务数据与工作流检查点', '服务器发送事件与实时进度推送',
  '后台调度与停滞面试恢复', '邮件模板与通知发送',
  'React 应用入口、路由与页面职责', 'API 客户端、认证状态与请求处理',
  'TanStack Query、表单与客户端校验', '候选人门户、音频采集与面试体验',
  'SSE 订阅与类型化事件处理', '无障碍 UI 基础组件、样式与共享组件',
  '后端测试策略与工作流测试替身', '前端类型检查、代码检查与生产构建',
  'Docker Compose、Nginx 与支持 SSE 的部署', '持久化文件、数据库备份与运维安全',
  '贯穿前后端的 API 功能开发', '候选人来源集成与未来扩展点',
];
const labels = {
  'Get Started': '入门指南', 'Deep Dive': '深入解析', 'Onboarding': '上手指南',
  'Architecture and Domain Model': '架构与领域模型', 'Interview Automation': '面试自动化',
  'Data, Services, and Integrations': '数据、服务与集成', 'Frontend Development': '前端开发',
  'Backend Services and Integration': '后端服务与集成',
  'Quality, Operations, and Extension': '质量、运维与扩展',
  'Beginner': '入门', 'Intermediate': '进阶', 'Advanced': '高级',
};

function scalar(config, name) {
  const raw = config.match(new RegExp(`^\\s*${name}:\\s*(.+)$`, 'm'))?.[1]?.trim();
  if (!raw) throw new Error(`Missing configuration: ${name}`);
  if (raw.startsWith('"')) return JSON.parse(raw);
  if (raw.startsWith("'")) return raw.slice(1, -1).replace(/''/g, "'");
  return raw;
}

function protect(markdown) {
  const tokens = [];
  const keep = value => {
    const token = `ZXQKEEP${String(tokens.length).padStart(5, '0')}QXZ`;
    tokens.push([token, value]);
    return token;
  };
  let text = markdown.replace(/^```([^\n]*)\n[\s\S]*?^```[^\n]*/gm, (block, lang) =>
    lang.trim() === 'mermaid' ? block : keep(block));
  text = text.replace(/`[^`\n]+`/g, keep);
  text = text.replace(/\]\(([^\n]*?)\)/g, (_, target) => `](${keep(target)})`);
  return {text, tokens};
}

async function main() {
  const config = await fs.readFile(path.join(os.homedir(), '.zread/config.yaml'), 'utf8');
  const base = scalar(config, 'base_url').replace(/\/$/, '');
  const key = scalar(config, 'api_key');
  const model = scalar(config, 'model');
  const endpoint = `${base}/chat/completions`;
  const catalog = JSON.parse(await fs.readFile(path.join(sourceDir, 'wiki.json'), 'utf8'));
  await fs.mkdir(targetDir, {recursive:true});
  let completed = 0;
  const queue = [...catalog.pages];

  async function translate(page) {
    const input = await fs.readFile(path.join(sourceDir, page.file), 'utf8');
    const {text, tokens} = protect(input);
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        const response = await fetch(endpoint, {
          method:'POST',
          headers:{'Content-Type':'application/json', Authorization:`Bearer ${key}`},
          signal:AbortSignal.timeout(240000),
          body:JSON.stringify({model, temperature:0.1, max_tokens:14000, messages:[
            {role:'system', content:'你是严谨的软件技术文档译者。将用户提供的现有英文 Markdown 完整翻译为简体中文，不重新编写或研究代码，不增删、总结、合并任何段落。保持原有 Markdown 标题层级、列表、表格、强调和顺序。所有自然语言，包括标题、表头、来源标签、链接显示文字，必须翻译为简体中文；技术名称保留。ZXQKEEP 开头 QXZ 结尾的占位符必须逐字原样保留，每个只出现一次，不要解释。Mermaid 图只翻译人类可见标签，不修改节点 ID、箭头和语法；标签必要时加双引号。仅输出翻译后的 Markdown，不添加外层代码块或说明。'},
            {role:'user', content:text}
          ]})
        });
        if (!response.ok) throw new Error(`Translation request HTTP ${response.status}`);
        const result = await response.json();
        if (result.choices?.[0]?.finish_reason === 'length') throw new Error('Translation was truncated');
        let output = result.choices?.[0]?.message?.content;
        if (typeof output !== 'string') throw new Error('Translation response has no text');
        for (const [token, value] of tokens) {
          if (output.split(token).length !== 2) throw new Error(`Protected content mismatch: ${token}`);
          output = output.replace(token, () => value);
        }
        if ((output.match(/[\u4e00-\u9fff]/g) || []).length < 100) throw new Error('Chinese translation missing');
        const headingCount = s => (s.match(/^#{1,6} /gm) || []).length;
        if (headingCount(input) !== headingCount(output)) throw new Error('Heading structure changed');
        await fs.writeFile(path.join(targetDir, page.file), output.trimEnd()+'\n', 'utf8');
        completed++;
        console.log(JSON.stringify({done:completed,total:catalog.pages.length,file:page.file}));
        return;
      } catch (error) {
        console.log(JSON.stringify({file:page.file,attempt,error:error.message}));
        if (attempt === 3) throw error;
      }
    }
  }
  await Promise.all(Array.from({length:3}, async () => {
    while(queue.length) {
      const page = queue.shift();
      const outputPath = path.join(targetDir, page.file);
      try {
        const existing = await fs.readFile(outputPath, 'utf8');
        if ((existing.match(/[\u4e00-\u9fff]/g)||[]).length > 100) {
          completed++; console.log(JSON.stringify({done:completed,total:catalog.pages.length,resumed:page.file})); continue;
        }
      } catch {}
      await translate(page);
    }
  }));
  catalog.id = targetId;
  catalog.language = 'zh-CN';
  catalog.generated_at = new Date().toISOString();
  catalog.pages.forEach((page, i) => {
    page.title = titles[i];
    for (const field of ['section','group','level']) {
      if (page[field]) {
        if (!labels[page[field]]) throw new Error(`Untranslated catalog label: ${page[field]}`);
        page[field] = labels[page[field]];
      }
    }
  });
  await fs.writeFile(path.join(targetDir,'wiki.json'),JSON.stringify(catalog,null,2)+'\n');
  await fs.writeFile(path.join(root,'current'),`versions/${targetId}\n`);
  console.log(JSON.stringify({state:'complete',pages:completed,version:targetId}));
}
main().catch(error => { console.error(error.message); process.exitCode=1; });
