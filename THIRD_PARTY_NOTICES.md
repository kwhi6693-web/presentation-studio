# Third-Party Notices / 第三方声明

Presentation Studio combines an original routing, retrieval, validation, and data-binding layer with pinned snapshots of four open-source projects. Each vendored project retains its own copyright notices and license file. Nothing in this repository removes or replaces upstream attribution.

Presentation Studio 将原创的路由、检索、校验和数据绑定层，与四个开源项目的锁定快照组合在一起。每个内置项目都保留自身的版权声明和许可证文件；本仓库不会删除或替换上游署名。

| Component / 组件 | Upstream / 上游 | Pinned commit / 锁定提交 | License / 许可证 | Vendored license / 内置许可证 |
|---|---|---|---|---|
| PPT Master | https://github.com/hugohe3/ppt-master | `ef0d585d5dc693d65be0b2aee5e8723b6264c367` | MIT | `presentation-studio/engines/ppt-master/LICENSE` |
| Guizang PPT Skill | https://github.com/op7418/guizang-ppt-skill | `c91369c449d34755d320a8b81d0734000d99d1ab` | AGPL-3.0 | `presentation-studio/engines/guizang/LICENSE` |
| Frontend Slides | https://github.com/zarazhangrui/frontend-slides | `9906a34d640d2111f724544cbc50f7f130569ae1` | MIT | `presentation-studio/engines/frontend-slides/LICENSE` |
| Baoyu Skills | https://github.com/JimLiu/baoyu-skills | `6b7a2e417500561a5ecdd0b168332f4142584617` | MIT | `presentation-studio/engines/baoyu/LICENSE` |

The machine-readable source of truth is [`presentation-studio/source-lock.json`](presentation-studio/source-lock.json). The engine role map is [`presentation-studio/engines/manifest.json`](presentation-studio/engines/manifest.json).

机器可读的来源真值位于 [`presentation-studio/source-lock.json`](presentation-studio/source-lock.json)，引擎职责映射位于 [`presentation-studio/engines/manifest.json`](presentation-studio/engines/manifest.json)。

## Repository-level licensing / 仓库层许可

Because this combined distribution includes an AGPL-3.0 component, the repository-level integration and distribution are provided under AGPL-3.0. Individually identified third-party components remain under their upstream licenses. Users and redistributors are responsible for complying with every applicable license. This notice is descriptive and is not legal advice.

由于本组合分发包含 AGPL-3.0 组件，仓库层的整合与分发采用 AGPL-3.0。已单独标识的第三方组件继续适用其上游许可证。使用者和再分发者应遵守所有适用许可证。本说明仅作事实描述，不构成法律意见。

