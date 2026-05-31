# Stage 36B 执行汇报：Studio 渲染模式 UI 接入

## 启动条件检查

- Stage 36A 报告是否已读取：待填写。
- capabilities 是否可用：待填写。
- ffmpeg_dsp_v0 是否可用：待填写。

## 完成情况

- 待填写：是否接入 capabilities。
- 待填写：是否新增输出模式选择。
- 待填写：是否发送 `render_engine`。
- 待填写：是否显示 `studio_effect_render_master`。
- 待填写：是否区分当前试听与当前主成品。

## 修改文件

- 待填写。

## UI 截图

```text
待填写
```

## UI 行为

- copy-only：待填写。
- ffmpeg_dsp_v0：待填写。
- ffmpeg 不可用降级：待填写。

## 验证结果

```text
node frontend\playwright_stage36b_studio_render_mode_smoke.cjs
结果：待填写

node frontend\playwright_stage35b_studio_version_ux_smoke.cjs
结果：待填写

node frontend\playwright_stage34b_effect_rack_export_ui_smoke.cjs
结果：待填写

node frontend\playwright_stage30b_studio_product_shell_smoke.cjs
结果：待填写

python -m pytest -q
结果：待填写

python -X utf8 backend\self_check.py
结果：待填写
```

## 风险与限制

- 待填写。

## 交接说明

- 待填写：下一阶段是否可以进入更细的波形/片段编辑。
- 待填写：是否还需要人工真机听感确认。
