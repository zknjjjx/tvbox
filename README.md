# tvbox

CineNest 公共影视源接口，GitHub Actions 每天 03:30（北京时间）自动从公开列表汇集、去重。不验活：各地网络不同，CineNest 会在本地测速并自动跳过连不上的源。

- `cmstv.json`：CineNest 专用接口，在 CineNest 首页「设置」里填它的地址
- `tvbox.json`：同一批源的 TVBox 配置（已去掉成人源）

地址（国内可用加速或 jsDelivr）：

- https://raw.githubusercontent.com/zknjjjx/tvbox/main/cmstv.json
- https://cdn.jsdelivr.net/gh/zknjjjx/tvbox@main/cmstv.json
- https://ghfast.top/https://raw.githubusercontent.com/zknjjjx/tvbox/main/cmstv.json

TVBox 把上面的 `cmstv.json` 换成 `tvbox.json` 即可。
