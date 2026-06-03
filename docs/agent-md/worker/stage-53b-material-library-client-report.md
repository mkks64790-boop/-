# Stage53-B 授权素材库客户端接入报告

## 范围

- 只改前端与本报告：`frontend/factory.html`、`frontend/js/factory/main.js`、`frontend/css/app.css`、`docs/agent-md/worker/stage-53b-material-library-client-report.md`。
- 未改 backend、未改数据库、未运行 UVR/RVC/训练、未删除历史数据。
- 保留 Stage52 `/api/separation/eval/sources` 读取路径，分离质检仍由原接口控制。

## UI 改动

- Factory 主区新增靠前的“授权素材库”抽屉，位置在“候选成品 / 需返工”后、“分离质量实验室”前。
- 抽屉常驻展示三类素材流向说明：
  - 干声训练基准：授权干声、干净人声、Sonovox demo stems，只用于训练/调音判断，不自动进入 UVR。
  - 分离评测混音：人工放入或合成的干净混音，只用于短片段分离质检。
  - 隔离/废弃素材：DJ 版、成品母带、来路不明或风险文件，只展示原因，不参与训练或分离测试。
- 原 Stage52 “授权/质检素材”小栏改名为“分离评测候选”，减少与素材库总入口混淆。

## 客户端降级态

- 前端会只读请求：
  - `/api/material-library/summary`
  - `/api/material-library/items`
- 当前本机探测结果：两个新接口均为 `404 Not Found`。
- 缺接口时页面只显示“等待地基接口”文案，不弹 toast，不阻断 Factory 页面加载。
- Stage52 `/api/separation/eval/sources` 当前为 `200`，仍独立渲染分离评测候选。

## 验证

- `cmd /c "python -c ""import sys; sys.stdout.buffer.write(open(r'frontend\js\factory\main.js','rb').read())"" | node --input-type=module --check"`：通过。
- 只读 Playwright smoke：通过。
  - 打开 `http://127.0.0.1:8000/factory`。
  - 展开“授权素材库”抽屉。
  - 确认三类用途说明、`/api/material-library/*` 等待态、“分离评测候选”入口均存在。
  - 无 `pageerror`，无危险非 GET 调用。

## 后端缺口

- 需要后端补 `/api/material-library/summary` 与 `/api/material-library/items`。
- 建议 items 至少返回素材 ID、标题/文件名、路径、时长、授权状态、素材角色、用途分组、风险/隔离原因，以及 `training_candidate_allowed`、`separation_eval_allowed` 两个布尔字段。
- 新素材库接口接入前，分离测试不要迁移到新接口，继续使用 Stage52 `/api/separation/eval/sources`。
