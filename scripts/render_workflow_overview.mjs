#!/usr/bin/env node
/** Generate the repository's editable SVG and high-resolution README PNG.
 * Optional rendering dependency: @resvg/resvg-js 2.6.2 (see docs/assets/README.md).
 * This script only renders documentation; it runs no inference or workflow tasks.
 */
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const fonts = [];
let rendererRoot = path.join(root, '.work/workflow-render');
let svgOnly = false;
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--font' && args[i + 1]) fonts.push(path.resolve(args[++i]));
  else if (args[i] === '--renderer-root' && args[i + 1]) rendererRoot = path.resolve(args[++i]);
  else if (args[i] === '--svg-only') svgOnly = true;
  else if (args[i] === '--help') {
    console.log('node scripts/render_workflow_overview.mjs [--font FONT] [--renderer-root DIR] [--svg-only]');
    process.exit(0);
  } else throw new Error('Unknown or incomplete option: ' + args[i]);
}
const version = readFileSync(path.join(root, 'pyproject.toml'), 'utf8').match(/^version = "([^"]+)"/m)[1];
const W = 1600, H = 1140;
const navy = '#18366A', body = '#34516F', muted = '#60778F';
const colors = {
  blue: {accent: '#4D94D5', border: '#A9CCED', panel: '#F0F7FF'},
  teal: {accent: '#24ADA5', border: '#99D9D3', panel: '#EDFAF7'},
  violet: {accent: '#8C76D6', border: '#C9BDF0', panel: '#F4F1FE'},
};
const xml = value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
const elements = [];
const rect = (x, y, w, h, fill, stroke, radius = 12, width = 1.2) => elements.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${radius}" fill="${fill}" stroke="${stroke}" stroke-width="${width}"/>`);
const text = (x, y, label, size = 18, weight = 400, fill = body, anchor = 'start') => elements.push(`<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${fill}" text-anchor="${anchor}">${xml(label)}</text>`);
const line = (d, stroke, width = 2, marker = '', dash = '') => elements.push(`<path d="${d}" fill="none" stroke="${stroke}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round"${marker ? ` marker-end="url(#${marker})"` : ''}${dash ? ` stroke-dasharray="${dash}"` : ''}/>`);

function icon(name, x, y, color, scale = 1) {
  const paths = {
    monitor: '<rect x="2" y="2" width="32" height="23" rx="3"/><path d="M18 25v8M8 33h20"/>',
    book: '<path d="M18 6C12 1 6 2 2 4v26c7-3 12-1 16 2 4-3 9-5 16-2V4c-4-2-10-3-16 2zM18 6v26"/>',
    layers: '<path d="M18 2L2 10l16 8 16-8zM2 18l16 8 16-8M2 26l16 8 16-8"/>',
    check: '<rect x="4" y="2" width="28" height="32" rx="4"/><path d="m10 17 5 5 11-12"/>',
    search: '<circle cx="15" cy="15" r="12"/><path d="m24 24 10 10M7 15h5l3-6 4 12 3-6h5"/>',
    tune: '<path d="M2 7h32M2 18h32M2 29h32"/><circle cx="11" cy="7" r="4" fill="white"/><circle cx="25" cy="18" r="4" fill="white"/><circle cx="13" cy="29" r="4" fill="white"/>',
    code: '<path d="m11 6-9 12 9 12M25 6l9 12-9 12M22 3l-8 30"/>',
    shield: '<path d="M18 2c5 5 11 6 15 6v10c0 9-8 14-15 17C11 32 3 27 3 18V8c4 0 10-1 15-6z"/><path d="m11 18 5 5 10-12"/>',
    network: '<rect x="11" y="1" width="14" height="10" rx="2"/><rect x="1" y="24" width="14" height="10" rx="2"/><rect x="21" y="24" width="14" height="10" rx="2"/><path d="M18 11v7M8 24v-6h20v6"/>',
    refresh: '<path d="M31 12A14 14 0 0 0 6 8L2 13m0-9v9h9M5 24a14 14 0 0 0 25 4l4-5m0 9v-9h-9"/>',
    chart: '<path d="M2 2v32h32M8 25l8-9 7 3 10-13"/><path d="M26 6h7v7"/>',
    archive: '<rect x="2" y="2" width="32" height="8" rx="2"/><rect x="2" y="15" width="32" height="8" rx="2"/><rect x="2" y="28" width="32" height="8" rx="2"/><path d="M7 6h2M7 19h2M7 32h2"/>',
    agent: '<circle cx="18" cy="18" r="7"/><circle cx="18" cy="2" r="3"/><circle cx="34" cy="18" r="3"/><circle cx="18" cy="34" r="3"/><circle cx="2" cy="18" r="3"/><path d="M18 5v6M25 18h6M18 25v6M5 18h6"/>',
  };
  elements.push(`<g transform="translate(${x} ${y}) scale(${scale})" fill="none" stroke="${color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">${paths[name]}</g>`);
}

function card(x, y, c, glyph, title, rows) {
  rect(x, y, 448, 107, '#FFFFFF', c.border, 11);
  icon(glyph, x + 15, y + 20, c.accent, .85);
  text(x + 60, y + 30, title, 21, 700, navy);
  rows.forEach((row, i) => text(x + 60, y + 59 + i * 25, row, row.startsWith('LightOp') ? 17 : 18));
}

function stage(x, color, number, title, subtitle, cards, footer) {
  const c = colors[color];
  rect(x, 236, 480, 640, c.panel, c.border, 15, 1.4);
  elements.push(`<circle cx="${x + 38}" cy="276" r="23" fill="${c.accent}"/>`);
  text(x + 38, 285, number, 26, 750, '#FFFFFF', 'middle');
  text(x + 76, 285, title, 25, 750, navy);
  text(x + 22, 316, subtitle, 16, 400, muted);
  cards.forEach((item, i) => {
    card(x + 16, 334 + i * 119, c, ...item);
    if (i < cards.length - 1) line(`M${x + 240} ${442 + i * 119}v9`, c.accent, 1.5, 'arrow-' + color);
  });
  rect(x + 16, 814, 448, 46, '#FFFFFF', c.border, 10);
  text(x + 240, 843, footer, 17, 650, navy, 'middle');
}

rect(0, 0, W, H, 'url(#page)', 'none', 0);
text(32, 58, 'HCU Infra Agent', 43, 800, navy);
text(34, 96, '面向 HCU 大模型推理的智能体协同工作流', 24, 600, navy);
rect(1124, 25, 444, 41, '#F2F7FE', '#B7D0EC', 9);
text(1346, 53, `SGLang · vLLM · v${version}`, 21, 600, navy, 'middle');
text(1346, 96, '部署 · 优化 · 扩容 · 独立分析', 19, 500, body, 'middle');

rect(32, 122, 1536, 92, '#F5F9FF', '#9FC3E8', 12, 1.4);
icon('agent', 61, 150, colors.blue.accent, 1.1);
text(120, 160, '统一主控 Agent', 28, 750, navy);
text(120, 190, '按证据拆解任务 · 按需协作 · 组织集成与独立复核', 18, 400, body);
['环境 / 部署', '分析 / 优化', '服务 / 运维'].forEach((label, i) => {
  rect(970 + i * 194, 138, 180, 37, '#FFFFFF', '#B6D0ED', 8);
  text(1060 + i * 194, 163, label, 18, 600, navy, 'middle');
});
text(1254, 199, '按范围选择模块 · 共享资源计时统一协调', 16, 400, muted, 'middle');
for (const x of [272, 800, 1328]) line(`M${x} 214v20`, '#7FAAD4', 1.8, 'arrow-blue');

stage(32, 'blue', '01', '环境检查与模型部署', '核对现场与适用配方，建立可复现起点', [
  ['monitor', '核对环境与资源', ['容器 / DTK / 框架 / 卡型与拓扑', '设备占用 · 依赖 · 目录与权限']],
  ['book', '检索配方与容量仿真', ['Cookbook · HCU-Knowledge', 'DCUSim：并行 / KV / 显存假设']],
  ['layers', '加载模型与适配缺口', ['架构 / 权重 / tokenizer / 量化', '缺模型支持或算子 → 适配与回归']],
  ['check', '冻结质量与性能基线', ['模型 · 请求 · 并发 · Cache · 版本', 'TTFT · TPOT · P95 · 吞吐（关闭Prof）']],
], '输出：启动配方 · 数值参考 · 基线结果');

stage(560, 'teal', '02', '性能分析与优化', '问题驱动 · 有界迭代 · 验证后保留', [
  ['search', 'Prof + TraceLens 定位瓶颈', ['Prefill / Decode · 多rank', '热点 · 通信 · 空泡 · 真实shape']],
  ['tune', '核查原生能力与优化假设', ['引擎 / 后端 / 通信 / KV路径', '配置调优 · 复用库 · 补齐算子能力']],
  ['code', '逐次探索与实现', ['独立候选 · 改动说明 · 原始证据', 'LightOp · Triton · TileLang · HIP · GEMM']],
  ['shield', '精度、性能与候选Prof验证', ['短 / 长输入 × 单请求 / 并发', '关闭Prof ≥3次对照 · 优化后Prof']],
], '独立复核：保留 / 回退 / 再迭代');

stage(1088, 'violet', '03', '扩容验证与服务运维', '基于已验证配置扩展，观察真实服务状态', [
  ['network', '扩容与服务验收', ['TP / EP / DP / PD · 部署配置', '质量 · SLA · 扩展效率 · 资源']],
  ['refresh', '故障诊断与受控恢复', ['卡住 / OOM / 泄漏 / 服务中断', '恢复责任明确 · 恢复后重新验证']],
  ['chart', '持续观察与事件处置', ['请求推进 · 吞吐 / 时延 / 失败率', '记录事件 → Agent处理 → 复核']],
  ['archive', '交付与经验整理', ['代码 · 配方 · 质量/性能 · 回退', '可复用结论沉淀，过程证据归档']],
], '达到目标或有依据停止 → 报告与交接');

line('M514 550h42', colors.blue.accent, 2.7, 'arrow-blue');
text(536, 538, '基线', 14, 600, muted, 'middle');
line('M1042 550h42', colors.blue.accent, 2.7, 'arrow-blue');
text(1064, 538, '通过', 14, 600, muted, 'middle');
icon('refresh', 995, 260, colors.teal.accent, .65);
line('M1328 877v18H800v-17', '#DA9A45', 1.8, 'arrow-orange', '5 4');
rect(978, 883, 172, 20, '#FFFFFF', 'none', 3);
text(1064, 898, '新瓶颈返回优化', 15, 600, '#AF742B', 'middle');

rect(32, 910, 1536, 62, '#F6FAFF', '#A9C9E8', 11);
icon('check', 54, 924, colors.blue.accent, .8);
text(100, 948, '证据与独立复核贯穿全程', 22, 700, navy);
const steps = [
  [472, 224, '执行 · 原始证据'], [720, 240, '精度 · 性能 · Prof'],
  [984, 206, '独立复核'], [1214, 332, '保留 / 回退 / 阶段推进'],
];
steps.forEach(([x, width, label], i) => {
  rect(x, 922, width, 38, '#FFFFFF', '#BDD4ED', 8);
  text(x + width / 2, 948, label, 18, 500, navy, 'middle');
  if (i < steps.length - 1) line(`M${x + width + 3} 941h16`, colors.blue.accent, 1.6, 'arrow-blue');
});

const supports = [
  [32, 'teal', 'book', '知识与工具贯穿全程', ['官方Cookbook · HCU-Knowledge', 'SimTools · Profiler · TraceLens · 算子库', '依据资料形成假设，以实测核验']],
  [560, 'blue', 'network', '协同与受控执行', ['本地 / SSH / Docker / Slurm / K8s', '固定快照 · 原件归档 · 未知执行先核查', 'BOARD / GUIDANCE / QUESTIONS']],
  [1088, 'violet', 'archive', '每轮归档与总报告', ['探索 · 精度 · 性能 · 优化前后Prof', '失败 / 中断记录 · 原件哈希 · 可导出', '总报告随迭代更新，保留完整探索历史']],
];
for (const [x, color, glyph, title, rows] of supports) {
  const c = colors[color];
  rect(x, 990, 480, 112, c.panel, c.border, 11);
  icon(glyph, x + 16, 1005, c.accent, .65);
  text(x + 52, 1023, title, 21, 700, navy);
  rows.forEach((label, i) => text(x + 20, 1048 + i * 22, label, 17));
}
text(800, 1129, '完整任务按阶段推进；独立请求按范围调用模块。宿主 Agent 会话承担实施与独立复核，运行和恢复设施按现场绑定。', 16, 400, muted, 'middle');

const markers = Object.entries({...colors, orange: {accent: '#DA9A45'}}).map(([name, c]) => `<marker id="arrow-${name}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L8 4L0 8Z" fill="${c.accent}"/></marker>`).join('');
const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-labelledby="title desc">
<title id="title">HCU Infra Agent 工作流总览</title>
<desc id="desc">统一主控协调环境检查与模型部署、性能分析与优化、扩容验证与服务运维。知识、工具、原始证据和独立复核贯穿全程；每轮输出探索、精度、性能和优化后的Prof，外层总报告持续更新。</desc>
<defs><linearGradient id="page" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#F7FAFE"/></linearGradient>${markers}</defs>
<style>text{font-family:'Noto Sans CJK SC','Microsoft YaHei','PingFang SC','Heiti SC',sans-serif}svg{shape-rendering:geometricPrecision;text-rendering:optimizeLegibility}</style>
${elements.join('\n')}
</svg>\n`;
let png;
if (!svgOnly) {
  const require = createRequire(path.join(rendererRoot, 'package.json'));
  const {Resvg} = require('@resvg/resvg-js');
  const image = new Resvg(svg, {fitTo: {mode: 'width', value: W * 2}, background: '#FFFFFF',
    font: {fontFiles: fonts, loadSystemFonts: true, defaultFontFamily: 'Heiti SC'}}).render();
  png = image.asPng();
}
const output = path.join(root, 'docs/assets');
mkdirSync(output, {recursive: true});
writeFileSync(path.join(output, 'workflow-overview.svg'), svg);
if (png) writeFileSync(path.join(output, 'workflow-overview.png'), png);
console.log(JSON.stringify({svg: 'docs/assets/workflow-overview.svg', png: png ? 'docs/assets/workflow-overview.png' : null, width: W, height: H, pngScale: 2}));
