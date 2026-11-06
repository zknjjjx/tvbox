# tvbox

公共影视接口，GitHub Actions 每天 03:30（北京时间）自动汇集更新。不验活、不测速。

- `cmstv.json`：CMS 采集站汇总，按人气（被多少个公开列表收录）排序，填到 CineNest 首页「设置」
- `niuniu.json`（妞妞）：电视用单仓配置，`tvbox.json` 内容相同（兼容旧地址）。，合并人气最高的几个仓库（饭太硬、肥猫、王二小、摸鱼儿、南风、菜妮丝……）的站点、解析、直播，再接上采集站（不含成人源）。站点名前缀是来源仓库
- `multi.json`：多仓配置（影视仓等支持多仓的软件），含上面的合并版和各原始仓库，单个仓库失效时可切换
- `upstream/`：各仓库最近一次成功拉取的明文配置，当天拉不到时用它兜底

仓库清单和顺序在 `scripts/repos.py` 的 `REPOS` 里，合并几个由 `MERGE_TOP`（默认 6）决定。

地址（国内可用加速或 jsDelivr）：

- https://raw.githubusercontent.com/zknjjjx/tvbox/main/niuniu.json
- https://cdn.jsdelivr.net/gh/zknjjjx/tvbox@main/niuniu.json
- https://ghfast.top/https://raw.githubusercontent.com/zknjjjx/tvbox/main/niuniu.json

把文件名换成 `multi.json` 或 `cmstv.json` 即得对应地址。
