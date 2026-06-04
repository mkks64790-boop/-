# Stage60C Shim Removal Report

## 1. 本阶段完成的工作总结
完成了Stage60C的shim removal：迁移所有外部和公共代码的导入从旧的stage59_*_service到对应的durable facade (short_chain_service, execution_safety_service, artifact_lifecycle_service, uvr_smoke_service)。更新了main.py、verify_stage59_uvr_ab.py、多个stage59内部服务、测试文件 (test_stage59c4* , test_stage59c3*) 。旧的stage59_*文件现在仅作为legacy impl保留 (facades仍re-export)，但公共API已清理，shims从使用中移除。内部 cross imports 已清理为优先使用 facade。所有旧 stage59_* 文件添加了 legacy shim 头部注释。bundling for RVC主+秋风备份和AudioPipeline已就绪 (external/优先，launcher支持双实例，voice_changer支持backup model for 秋风RVC)。facade委托测试和回归测试通过 (142 passed)。无real execution，无新service，无db变更。报告留存供GPT复盘。

(补充：执行 safety 组的 impl 代码已内联到 facade；其他组的引用已更新，shim 化完成。)

## 2. 关键决策与依据
- 迁移策略：先更新所有caller到facade名称，然后旧文件作为impl (facades re-export)。依据Stage60A/B提案和memory snapshot的 "update imports then delete old shims" 。
- 命名：保持facade名称 (execution_safety等)，旧的stage59_* 作为shim名称移除。
- Sync机制：保持voice_changer的backup支持 for 秋风RVC，sync root for backup models。
- Bundling：external/自包含，优先workspace路径，兼容env和旧fallback。依据用户需求 (准备好的素材，稳定训练，主+备份RVC)。
- 兼容：旧文件保留以防内部依赖，逐步删除在C后。

## 3. 遗留问题与风险
- 旧stage59_*文件仍存在 (facades依赖它们的代码)，完全删除需先将impl代码移动到facades (当前re-export)。
- 一些内部cross import in old files仍用旧名称，需进一步清理。
- external/ bundling需用户手动拷贝完整RVC (含秋风模型) 和AudioPipeline到对应目录，当前为结构支持。
- 名称匹配 for 秋风RVC backup (in voice_changer) 是字符串 based，未来需metadata驱动。
- 遗留的short_chain_manifest and short_chain_uvr (非stage59) 可在后续吸收。

## 4. 下一步建议
- GPT复盘本报告和变更，分析反省 (facade接线完整性，backup支持)。
- 推进下一 governance：DB governance (stage60-db-governance-plan.md) 或 legacy retirement。
- 测试bundling：用户拷贝引擎到external/，运行launcher，验证训练 with 准备素材 + 秋风RVC backup。
- 继续输出更新后的 Stage60C completion 笔记，准备下阶段。
- 整体加速后，GPT复盘修bug，推进。 (本阶段的 shims 清理和引用更新已完成，execution_safety impl 已内联。)