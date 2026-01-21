![:name](https://count.getloli.com/@astrbot_plugin_animewifex?name=astrbot_plugin_animewifex&theme=capoo-2&padding=7&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# Aastrbot_plugin_animewifex

原插件：https://github.com/zgojin/astrbot_plugin_AW

在此基础上添加了几个功能，更改了数据目录，支持插件面板配置。

**本插件代码为AI生成，下面图床的也是。**

配套图床：https://github.com/monbed/wife

从GitHub获取：如果你的BOT能够正常访问GitHub获取图片，图片服务器基础 URL填写：https://raw.githubusercontent.com/monbed/wife/main/ 图片列表 URL填写：https://animewife.dpdns.org/list.txt

也可以手动下载图片，放入AstrBot\data\plugin_data\astrbot_plugin_animewifex\img\wife目录。

## 指令 ##
- `老婆帮助` 显示所有命令帮助
- `抽老婆` 每天一次，随机抽一张二次元老婆
- `查老婆` 查看今日老婆 加@可以查看别人老婆（支持不@昵称匹配）
- `牛老婆` @用户概率牛别人老婆（支持不@昵称匹配）
- `重置牛` 重置牛老婆次数，也可@用户重置别人的次数，失败禁言，AstrBot管理员权限不受限制。
- `切换ntr开关状态` 管理员命令，开启/关闭牛老婆功能
- `换老婆` 重新抽取老婆
- `重置换` 重置换老婆次数，其余同重置牛，与重置牛共享次数
- `交换老婆` @用户和对方交换老婆 
- `同意交换` @用户同意
- `拒绝交换` @用户拒绝
- `查看交换请求` 查看交换老婆请求

## 更新日志 ##
v1.5.5：完善交换老婆逻辑，牛老婆成功后立刻显示。

v1.5.6：老婆信息显示出处，需要更新图包。

v1.5.7：现在交换老婆成功也会清理其它交换请求。

v1.5.8：润色各种提示信息。

v1.5.9：使用!代替#拼接老婆出处与名称，解决图床访问问题。

v1.6.0：添加重置换老婆功能，重置功能合并，共享使用次数。

v1.6.1：修复重置换老婆逻辑。

v1.6.2：添加logo。

v1.6.3：支持从GitHub获取图片。

v1.6.4：优化老婆名称显示，过滤路径前缀。

v1.6.5：重大更新：添加并发锁保护，支持多用户同时操作；合并记录文件；添加老婆帮助命令；支持前缀开关配置；代码结构优化。

v1.6.6：修改昵称匹配方式为完整昵称匹配。

v1.6.7：修改为仅对群触发。

v1.6.8：修复牛老婆和交换老婆的数据交换逻辑。

v1.6.9：修复群消息监听中发送未注册命令导致的属性访问异常。

v1.7.0：去除牛老婆成功立刻显示。

## 相关
- [astrbot_plugin_AW](https://github.com/zgojin/astrbot_plugin_AW)
- [Astrbot](https://astrbot.app/)
