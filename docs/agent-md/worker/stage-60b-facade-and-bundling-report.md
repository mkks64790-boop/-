# Stage60B Facade Introduction and Engine Bundling Report

## 1. 本阶段完成的工作总结
- 完成了4个durable facade的引入和接线：short_chain_service、execution_safety_service、artifact_lifecycle_service、uvr_smoke_service作为稳定入口，旧stage59_*模块作为delegate保留零变更。
- 完成RVC主引擎（external/rvc-webui，7866）和秋风RVC备份（external/rvc-webui-backup，7865）+ AudioPipeline（external/audio-pipeline）的workspace bundling，实现自包含稳定训练环境。
- 中心化路径到engine_paths.py，更新voice_changer、model_trainer、vocal_separator、launcher、engine_manager支持external优先 + backup实例自动启动。
- 增强voice_changer支持根据model origin或名称（秋风/qiufeng）选择backup实例，并支持sync root参数用于备份模型同步。
- 迁移main.py、verify_stage59_uvr_ab.py、多个stage59内部服务导入到facade，添加facade委托测试。
- 更新external/README和子目录说明，支持用户拷贝完整部署（含秋风模型）。
- 所有变更保持现有cover/train/studio行为不变，pytest相关测试通过，无raw资产入git。

## 2. 关键决策与依据
- Facade命名和结构：依据Stage60A提案和consolidation plan，使用execution_safety等名称，facade re-export旧实现作为迁移起点。
- 迁移策略：facade先立，delegate旧模块，逐步更新caller（main、verify、内部），shims删除留Stage60C。避免循环导入和行为变更。
- Bundling策略：external/作为自包含位置，优先于D:\外部；primary训练+推理，backup仅inference；launcher支持双实例；model metadata记录origin。依据用户素材准备就绪、需稳定训练、秋风RVC作为studio备用需求。
- Sync机制：voice_changer _sync支持root参数，backup模型sync到backup weights；engine_paths提供rvc_engine_paths(kind)统一选择。
- 兼容：env override优先，旧路径fallback保留。

## 3. 遗留问题与风险
- 旧stage59_*仍有内部直接引用，facade接线不完整，需Stage60C清理。
- external/目前仅结构，用户需手动拷贝完整RVC（主+秋风）和AudioPipeline；setup脚本为辅助。
- backup模型选择依赖名称/ origin字符串匹配，未来需更robust metadata驱动。
- self_check RUNTIME仍依赖外部引擎完整性，bundling后需用户填充才能PASS。
- 无新DB schema，legacy tasks/voice_assets仍存，DB governance留后。

## 4. 下一步建议
- 人工复盘本报告和变更，确认bundling可用于训练。
- 用户拷贝完整引擎到external/对应目录，运行launcher验证主+秋风备份可用，测试用准备素材训练RVC。
- 准备Stage60C prompt：shim删除 + 最终迁移 + facade纯化。
- GPT复盘后，反省本次（facade接线、backup支持），修小bug（如名称匹配），推进Stage60C或直接训练使用。
- 继续governance节奏，每步留report/memory。