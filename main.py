from astrbot.api.all import *
from astrbot.api.star import StarTools
from datetime import datetime, timedelta
import random
import os
import re
import json
import aiohttp
import asyncio

# ==================== 常量定义 ====================

PLUGIN_DIR = StarTools.get_data_dir("astrbot_plugin_animewifex")
CONFIG_DIR = os.path.join(PLUGIN_DIR, "config")
IMG_DIR = os.path.join(PLUGIN_DIR, "img", "wife")

# 确保目录存在
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

# 数据文件路径
RECORDS_FILE = os.path.join(CONFIG_DIR, "records.json")
SWAP_REQUESTS_FILE = os.path.join(CONFIG_DIR, "swap_requests.json")
NTR_STATUS_FILE = os.path.join(CONFIG_DIR, "ntr_status.json")

# ==================== 全局数据存储 ====================

records = {  # 统一的记录数据结构
    "ntr": {},        # 牛老婆记录
    "change": {},     # 换老婆记录
    "reset": {},      # 重置使用次数
    "swap": {}        # 交换老婆请求次数
}
swap_requests = {}  # 交换请求数据
ntr_statuses = {}  # NTR 开关状态

# ==================== 并发锁 ====================

config_locks = {}      # 群组配置锁
records_lock = asyncio.Lock()  # 记录数据锁
swap_lock = asyncio.Lock()     # 交换请求锁
ntr_lock = asyncio.Lock()      # NTR 状态锁


def get_config_lock(group_id: str) -> asyncio.Lock:
    """获取或创建群组配置锁"""
    if group_id not in config_locks:
        config_locks[group_id] = asyncio.Lock()
    return config_locks[group_id]

def get_today():
    """获取当前上海时区日期字符串"""
    utc_now = datetime.utcnow()
    return (utc_now + timedelta(hours=8)).date().isoformat()


def load_json(path: str) -> dict:
    """安全加载 JSON 文件"""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_json(path: str, data: dict) -> None:
    """保存数据到 JSON 文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def load_group_config(group_id: str) -> dict:
    """加载群组配置"""
    return load_json(os.path.join(CONFIG_DIR, f"{group_id}.json"))


def save_group_config(group_id: str, config: dict) -> None:
    """保存群组配置"""
    save_json(os.path.join(CONFIG_DIR, f"{group_id}.json"), config)


def load_ntr_statuses():
    """加载 NTR 开关状态"""
    raw = load_json(NTR_STATUS_FILE)
    ntr_statuses.clear()
    ntr_statuses.update(raw)


def save_ntr_statuses():
    """保存 NTR 开关状态"""
    save_json(NTR_STATUS_FILE, ntr_statuses)


# ==================== 数据加载和保存函数 ====================

def load_records():
    """加载所有记录数据"""
    raw = load_json(RECORDS_FILE)
    records.clear()
    records.update({
        "ntr": raw.get("ntr", {}),
        "change": raw.get("change", {}),
        "reset": raw.get("reset", {}),
        "swap": raw.get("swap", {})
    })


def save_records():
    """保存所有记录数据"""
    save_json(RECORDS_FILE, records)


def load_swap_requests():
    """加载交换请求并清理过期数据"""
    raw = load_json(SWAP_REQUESTS_FILE)
    today = get_today()
    cleaned = {}
    
    for gid, reqs in raw.items():
        valid = {uid: rec for uid, rec in reqs.items() if rec.get("date") == today}
        if valid:
            cleaned[gid] = valid
    
    globals()["swap_requests"] = cleaned
    if raw != cleaned:
        save_json(SWAP_REQUESTS_FILE, cleaned)


def save_swap_requests():
    """保存交换请求"""
    save_json(SWAP_REQUESTS_FILE, swap_requests)


# 初始加载所有数据
load_records()
load_swap_requests()
load_ntr_statuses()

# ==================== 主插件类 ====================


@register(
    "astrbot_plugin_animewifex",
    "monbed",
    "群二次元老婆插件修改版",
    "1.6.5",
    "https://github.com/monbed/astrbot_plugin_animewifex",
)
class WifePlugin(Star):
    """二次元老婆插件主类"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._init_config()
        self._init_commands()
        self.admins = self.load_admins()

    def _init_config(self):
        """初始化配置参数"""
        self.need_prefix = self.config.get("need_prefix")
        self.ntr_max = self.config.get("ntr_max")
        self.ntr_possibility = self.config.get("ntr_possibility")
        self.change_max_per_day = self.config.get("change_max_per_day")
        self.swap_max_per_day = self.config.get("swap_max_per_day")
        self.reset_max_uses_per_day = self.config.get("reset_max_uses_per_day")
        self.reset_success_rate = self.config.get("reset_success_rate")
        self.reset_mute_duration = self.config.get("reset_mute_duration")
        self.image_base_url = self.config.get("image_base_url")
        self.image_list_url = self.config.get("image_list_url")

    def _init_commands(self):
        """初始化命令映射表"""
        self.commands = {
            "老婆帮助": self.wife_help,
            "抽老婆": self.animewife,
            "查老婆": self.search_wife,
            "牛老婆": self.ntr_wife,
            "重置牛": self.reset_ntr,
            "切换ntr开关状态": self.switch_ntr,
            "换老婆": self.change_wife,
            "重置换": self.reset_change_wife,
            "交换老婆": self.swap_wife,
            "同意交换": self.agree_swap_wife,
            "拒绝交换": self.reject_swap_wife,
            "查看交换请求": self.view_swap_requests,
        }

    def load_admins(self) -> list:
        """加载管理员列表"""
        path = os.path.join("data", "cmd_config.json")
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
                admins = cfg.get("admins_id", [])
                return [str(admin_id) for admin_id in admins]
        except Exception:
            return []

    def parse_at_target(self, event: AstrMessageEvent) -> str | None:
        """解析消息中的@目标用户"""
        for comp in event.message_obj.message:
            if isinstance(comp, At):
                return str(comp.qq)
        return None

    def parse_target(self, event: AstrMessageEvent) -> str | None:
        """解析命令目标用户（支持@和昵称模糊匹配）"""
        target = self.parse_at_target(event)
        if target:
            return target
        
        msg = event.message_str.strip()
        if msg.startswith("牛老婆") or msg.startswith("查老婆"):
            parts = msg.split(maxsplit=1)
            if len(parts) > 1:
                name = parts[1]
                group_id = str(event.message_obj.group_id)
                cfg = load_group_config(group_id)
                for uid, data in cfg.items():
                    if not isinstance(data, list):
                        continue
                    if re.search(re.escape(name), data[2], re.IGNORECASE):
                        return uid
        return None

    # ==================== 消息处理 ====================

    @event_message_type(EventMessageType.ALL)
    async def on_all_messages(self, event: AstrMessageEvent):
        """消息分发处理"""
        if not hasattr(event.message_obj, "group_id"):
            return
        
        # 检查是否需要前缀唤醒
        if self.need_prefix and not event.is_at_or_wake_command:
            return
        
        text = event.message_str.strip()
        for cmd, func in self.commands.items():
            if text.startswith(cmd):
                async for res in func(event):
                    yield res
                break

    # ==================== 抽老婆相关 ====================

    async def animewife(self, event: AstrMessageEvent):
        """抽老婆"""
        gid = str(event.message_obj.group_id)
        uid = str(event.get_sender_id())
        nick = event.get_sender_name()
        today = get_today()
        
        async with get_config_lock(gid):
            cfg = load_group_config(gid)
            wife_data = cfg.get(uid)
            
            if not wife_data or not isinstance(wife_data, list) or wife_data[1] != today:
                # 今天还没抽，获取新老婆
                img = await self._fetch_wife_image()
                if not img:
                    yield event.plain_result("抱歉，今天的老婆获取失败了，请稍后再试~")
                    return
                cfg[uid] = [img, today, nick]
                save_group_config(gid, cfg)
            else:
                img = wife_data[0]
        
        # 生成并发送消息
        yield event.chain_result(self._build_wife_message(img, nick))

    async def _fetch_wife_image(self) -> str | None:
        """获取老婆图片"""
        # 优先使用本地图片
        try:
            local_imgs = os.listdir(IMG_DIR)
            if local_imgs:
                return random.choice(local_imgs)
        except Exception:
            pass
        
        # 从网络获取
        try:
            url = self.image_list_url or self.image_base_url
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        return random.choice(text.splitlines())
        except Exception:
            pass
        
        return None

    def _build_wife_message(self, img: str, nick: str):
        """构建老婆消息链"""
        name = os.path.splitext(img)[0].split("/")[-1]
        
        if "!" in name:
            source, chara = name.split("!", 1)
            text = f"{nick}，你今天的老婆是来自《{source}》的{chara}，请好好珍惜哦~"
        else:
            text = f"{nick}，你今天的老婆是{name}，请好好珍惜哦~"
        
        path = os.path.join(IMG_DIR, img)
        try:
            chain = [
                Plain(text),
                (
                    Image.fromFileSystem(path)
                    if os.path.exists(path)
                    else Image.fromURL(self.image_base_url + img)
                ),
            ]
            return chain
        except Exception:
            return [Plain(text)]

    # ==================== 帮助命令 ====================

    async def wife_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        help_text = """
【基础命令】
• 抽老婆 - 每天抽取一个二次元老婆
• 查老婆 [@用户] - 查看别人的老婆

【牛老婆功能】(概率较低😭)
• 牛老婆 [@用户] - 有概率抢走别人的老婆
• 重置牛 [@用户] - 重置牛的次数(失败会禁言)

【换老婆功能】
• 换老婆 - 丢弃当前老婆换新的
• 重置换 [@用户] - 重置换老婆的次数(失败会禁言)

【交换功能】
• 交换老婆 [@用户] - 向别人发起老婆交换请求
• 同意交换 [@发起者] - 同意交换请求
• 拒绝交换 [@发起者] - 拒绝交换请求
• 查看交换请求 - 查看当前的交换请求

【管理员命令】
• 切换ntr开关状态 - 开启/关闭NTR功能

💡 提示：部分命令有每日使用次数限制
"""
        yield event.plain_result(help_text.strip())

    async def search_wife(self, event: AstrMessageEvent):
        """查老婆"""
        gid = str(event.message_obj.group_id)
        tid = self.parse_target(event) or str(event.get_sender_id())
        today = get_today()
        
        async with get_config_lock(gid):
            cfg = load_group_config(gid)
            wife_data = cfg.get(tid)
            
            if not wife_data or not isinstance(wife_data, list) or wife_data[1] != today:
                yield event.plain_result("没有发现老婆的踪迹，快去抽一个试试吧~")
                return
            
            img, _, owner = wife_data
        
        name = os.path.splitext(img)[0].split("/")[-1]
        
        if "!" in name:
            source, chara = name.split("!", 1)
            text = f"{owner}的老婆是来自《{source}》的{chara}，羡慕吗？"
        else:
            text = f"{owner}的老婆是{name}，羡慕吗？"
        
        path = os.path.join(IMG_DIR, img)
        try:
            chain = [
                Plain(text),
                (
                    Image.fromFileSystem(path)
                    if os.path.exists(path)
                    else Image.fromURL(self.image_base_url + img)
                ),
            ]
            yield event.chain_result(chain)
        except Exception:
            yield event.plain_result(text)

    # ==================== 牛老婆相关 ====================

    async def ntr_wife(self, event: AstrMessageEvent):
        """牛老婆"""
        gid = str(event.message_obj.group_id)
        uid = str(event.get_sender_id())
        nick = event.get_sender_name()
        
        # 检查 NTR 功能是否启用
        if not ntr_statuses.get(gid, True):
            yield event.plain_result("牛老婆功能还没开启哦，请联系管理员开启~")
            return
        
        today = get_today()
        
        async with records_lock:
            grp = records["ntr"].setdefault(gid, {})
            rec = grp.get(uid, {"date": today, "count": 0})
            
            if rec["date"] != today:
                rec = {"date": today, "count": 0}
            
            if rec["count"] >= self.ntr_max:
                yield event.plain_result(f"{nick}，你今天已经牛了{self.ntr_max}次啦，明天再来吧~")
                return
        
        # 获取目标用户
        tid = self.parse_target(event)
        if not tid or tid == uid:
            msg = "请@你想牛的对象哦~" if not tid else "不能牛自己呀，换个人试试吧~"
            yield event.plain_result(f"{nick}，{msg}")
            return
        
        # 检查目标是否有老婆并执行牛操作
        async with get_config_lock(gid):
            cfg = load_group_config(gid)
            if tid not in cfg or cfg[tid][1] != today:
                yield event.plain_result("对方今天还没有老婆可牛哦~")
                return
            
            # 更新牛的次数
            async with records_lock:
                rec["count"] += 1
                grp[uid] = rec
                save_records()
            
            # 判断牛老婆是否成功
            if random.random() < self.ntr_possibility:
                # 牛成功：目标用户的老婆转给牛者
                wife_info = cfg[tid]
                cfg[uid] = wife_info
                del cfg[tid]
                save_group_config(gid, cfg)
                
                # 取消相关交换请求
                cancel_msg = await self.cancel_swap_on_wife_change(gid, [uid, tid])
                
                img = wife_info[0]
                yield event.plain_result(f"{nick}，牛老婆成功！老婆已归你所有，恭喜恭喜~")
                if cancel_msg:
                    yield event.plain_result(cancel_msg)
                
                # 显示获得的老婆
                yield event.chain_result(self._build_wife_message(img, nick))
            else:
                rem = self.ntr_max - rec["count"]
                yield event.plain_result(f"{nick}，很遗憾，牛失败了！你今天还可以再试{rem}次~")

    async def switch_ntr(self, event: AstrMessageEvent):
        """切换 NTR 开关（仅管理员）"""
        uid = str(event.get_sender_id())
        nick = event.get_sender_name()
        
        if uid not in self.admins:
            yield event.plain_result(f"{nick}，你没有权限操作哦~")
            return
        
        gid = str(event.message_obj.group_id)
        async with ntr_lock:
            current_status = ntr_statuses.get(gid, True)
            ntr_statuses[gid] = not current_status
            save_ntr_statuses()
        
        state = "开启" if not current_status else "关闭"
        yield event.plain_result(f"{nick}，NTR已{state}")

    # ==================== 换老婆相关 ====================

    async def change_wife(self, event: AstrMessageEvent):
        """换老婆"""
        gid = str(event.message_obj.group_id)
        uid = str(event.get_sender_id())
        nick = event.get_sender_name()
        today = get_today()
        
        async with records_lock:
            # 检查每日换老婆次数
            recs = records["change"].setdefault(gid, {})
            rec = recs.get(uid, {"date": "", "count": 0})
            
            if rec["date"] == today and rec["count"] >= self.change_max_per_day:
                yield event.plain_result(f"{nick}，你今天已经换了{self.change_max_per_day}次老婆啦，明天再来吧~")
                return
        
        # 检查是否有老婆并删除
        async with get_config_lock(gid):
            cfg = load_group_config(gid)
            if uid not in cfg or cfg[uid][1] != today:
                yield event.plain_result(f"{nick}，你今天还没有老婆，先去抽一个再来换吧~")
                return
            
            # 删除老婆
            del cfg[uid]
            save_group_config(gid, cfg)
        
        # 更新记录
        async with records_lock:
            if rec["date"] != today:
                rec = {"date": today, "count": 1}
            else:
                rec["count"] += 1
            recs[uid] = rec
            save_records()
        
        # 取消相关交换请求
        cancel_msg = await self.cancel_swap_on_wife_change(gid, [uid])
        if cancel_msg:
            yield event.plain_result(cancel_msg)
        
        # 立即展示新老婆
        async for res in self.animewife(event):
            yield res

    # ==================== 重置相关 ====================

    async def reset_ntr(self, event: AstrMessageEvent):
        """重置牛老婆次数"""
        gid = str(event.message_obj.group_id)
        uid = str(event.get_sender_id())
        nick = event.get_sender_name()
        today = get_today()
        
        # 管理员可直接重置他人
        if uid in self.admins:
            tid = self.parse_at_target(event) or uid
            async with records_lock:
                if gid in records["ntr"] and tid in records["ntr"][gid]:
                    del records["ntr"][gid][tid]
                    save_records()
            yield event.chain_result([
                Plain("管理员操作：已重置"), At(qq=int(tid)), Plain("的牛老婆次数。")
            ])
            return
        
        # 普通用户使用重置机会
        async with records_lock:
            grp = records["reset"].setdefault(gid, {})
            rec = grp.get(uid, {"date": today, "count": 0})
            
            if rec.get("date") != today:
                rec = {"date": today, "count": 0}
            
            if rec["count"] >= self.reset_max_uses_per_day:
                yield event.plain_result(f"{nick}，你今天已经用完{self.reset_max_uses_per_day}次重置机会啦，明天再来吧~")
                return
            
            rec["count"] += 1
            grp[uid] = rec
            save_records()
        
        tid = self.parse_at_target(event) or uid
        
        if random.random() < self.reset_success_rate:
            async with records_lock:
                if gid in records["ntr"] and tid in records["ntr"][gid]:
                    del records["ntr"][gid][tid]
                    save_records()
            yield event.chain_result([
                Plain("已重置"), At(qq=int(tid)), Plain("的牛老婆次数。")
            ])
        else:
            try:
                await event.bot.set_group_ban(group_id=int(gid), user_id=int(uid), duration=self.reset_mute_duration)
            except Exception:
                pass
            yield event.plain_result(f"{nick}，重置牛失败，被禁言{self.reset_mute_duration}秒，下次记得再接再厉哦~")

    async def reset_change_wife(self, event: AstrMessageEvent):
        """重置换老婆次数"""
        gid = str(event.message_obj.group_id)
        uid = str(event.get_sender_id())
        nick = event.get_sender_name()
        today = get_today()
        
        # 管理员可直接重置他人
        if uid in self.admins:
            tid = self.parse_at_target(event) or uid
            async with records_lock:
                grp = records["change"].setdefault(gid, {})
                if tid in grp:
                    del grp[tid]
                    save_records()
            yield event.chain_result([
                Plain("管理员操作：已重置"), At(qq=int(tid)), Plain("的换老婆次数。")
            ])
            return
        
        # 普通用户使用重置机会
        async with records_lock:
            grp = records["reset"].setdefault(gid, {})
            rec = grp.get(uid, {"date": today, "count": 0})
            
            if rec.get("date") != today:
                rec = {"date": today, "count": 0}
            
            if rec["count"] >= self.reset_max_uses_per_day:
                yield event.plain_result(f"{nick}，你今天已经用完{self.reset_max_uses_per_day}次重置机会啦，明天再来吧~")
                return
            
            rec["count"] += 1
            grp[uid] = rec
            save_records()
        
        tid = self.parse_at_target(event) or uid
        
        if random.random() < self.reset_success_rate:
            async with records_lock:
                grp2 = records["change"].setdefault(gid, {})
                if tid in grp2:
                    del grp2[tid]
                    save_records()
            yield event.chain_result([
                Plain("已重置"), At(qq=int(tid)), Plain("的换老婆次数。")
            ])
        else:
            try:
                await event.bot.set_group_ban(group_id=int(gid), user_id=int(uid), duration=self.reset_mute_duration)
            except Exception:
                pass
            yield event.plain_result(f"{nick}，重置换失败，被禁言{self.reset_mute_duration}秒，下次记得再接再厉哦~")

    # ==================== 交换老婆相关 ====================

    async def swap_wife(self, event: AstrMessageEvent):
        """发起交换老婆请求"""
        gid = str(event.message_obj.group_id)
        uid = str(event.get_sender_id())
        tid = self.parse_at_target(event)
        nick = event.get_sender_name()
        today = get_today()
        
        async with records_lock:
            # 检查每日交换请求次数
            grp_limit = records["swap"].setdefault(gid, {})
            rec_lim = grp_limit.get(uid, {"date": "", "count": 0})
            
            if rec_lim["date"] != today:
                rec_lim = {"date": today, "count": 0}
            
            if rec_lim["count"] >= self.swap_max_per_day:
                yield event.plain_result(f"{nick}，你今天已经发起了{self.swap_max_per_day}次交换请求啦，明天再来吧~")
                return
        
        if not tid or tid == uid:
            yield event.plain_result(f"{nick}，请在命令后@你想交换的对象哦~")
            return
        
        # 检查双方是否都有老婆
        async with get_config_lock(gid):
            cfg = load_group_config(gid)
            for x in (uid, tid):
                if x not in cfg or cfg[x][1] != today:
                    who = nick if x == uid else "对方"
                    yield event.plain_result(f"{who}，今天还没有老婆，无法进行交换哦~")
                    return
        
        # 记录交换请求
        async with records_lock:
            rec_lim["count"] += 1
            grp_limit[uid] = rec_lim
            save_records()
        
        async with swap_lock:
            grp = swap_requests.setdefault(gid, {})
            grp[uid] = {"target": tid, "date": today}
            save_swap_requests()
        
        yield event.chain_result([
            Plain(f"{nick} 想和 "), At(qq=int(tid)),
            Plain(" 交换老婆啦！请对方用\"同意交换 @发起者\"或\"拒绝交换 @发起者\"来回应~")
        ])

    async def agree_swap_wife(self, event: AstrMessageEvent):
        """同意交换老婆"""
        gid = str(event.message_obj.group_id)
        tid = str(event.get_sender_id())
        uid = self.parse_at_target(event)
        nick = event.get_sender_name()
        
        # 检查和删除交换请求（原子操作）
        async with swap_lock:
            grp = swap_requests.get(gid, {})
            rec = grp.get(uid)
            
            if not rec or rec.get("target") != tid:
                yield event.plain_result(f"{nick}，请在命令后@发起者，或用\"查看交换请求\"命令查看当前请求哦~")
                return
            
            # 删除请求
            del grp[uid]
        
        # 执行交换
        async with get_config_lock(gid):
            cfg = load_group_config(gid)
            cfg[uid][0], cfg[tid][0] = cfg[tid][0], cfg[uid][0]
            save_group_config(gid, cfg)
        
        # 保存交换请求删除
        save_swap_requests()
        
        # 取消相关交换请求
        cancel_msg = await self.cancel_swap_on_wife_change(gid, [uid, tid])
        
        yield event.plain_result("交换成功！你们的老婆已经互换啦，祝幸福~")
        if cancel_msg:
            yield event.plain_result(cancel_msg)

    async def reject_swap_wife(self, event: AstrMessageEvent):
        """拒绝交换老婆"""
        gid = str(event.message_obj.group_id)
        tid = str(event.get_sender_id())
        uid = self.parse_at_target(event)
        nick = event.get_sender_name()
        
        async with swap_lock:
            grp = swap_requests.get(gid, {})
            rec = grp.get(uid)
            
            if not rec or rec.get("target") != tid:
                yield event.plain_result(f"{nick}，请在命令后@发起者，或用\"查看交换请求\"命令查看当前请求哦~")
                return
            
            del grp[uid]
            save_swap_requests()
        
        yield event.chain_result([
            At(qq=int(uid)), Plain("，对方婉拒了你的交换请求，下次加油吧~")
        ])

    async def view_swap_requests(self, event: AstrMessageEvent):
        """查看当前交换请求"""
        gid = str(event.message_obj.group_id)
        me = str(event.get_sender_id())
        
        grp = swap_requests.get(gid, {})
        cfg = load_group_config(gid)
        
        # 获取发起的和收到的请求
        sent_targets = [rec["target"] for uid, rec in grp.items() if uid == me]
        received_from = [uid for uid, rec in grp.items() if rec.get("target") == me]
        
        if not sent_targets and not received_from:
            yield event.plain_result("你当前没有任何交换请求哦~")
            return
        
        parts = []
        for tid in sent_targets:
            name = cfg.get(tid, [None, None, "未知用户"])[2]
            parts.append(f"→ 你发起给 {name} 的交换请求")
        
        for uid in received_from:
            name = cfg.get(uid, [None, None, "未知用户"])[2]
            parts.append(f"→ {name} 发起给你的交换请求")
        
        text = "当前交换请求如下：\n" + "\n".join(parts) + "\n请在\"同意交换\"或\"拒绝交换\"命令后@发起者进行操作~"
        yield event.plain_result(text)

    # ==================== 辅助方法 ====================

    async def cancel_swap_on_wife_change(self, gid: str, user_ids: list) -> str | None:
        """检查并取消与指定用户相关的交换请求"""
        today = get_today()
        grp = swap_requests.get(gid, {})
        grp_limit = records["swap"].setdefault(gid, {})
        
        # 找出需要取消的交换请求
        to_cancel = [
            req_uid for req_uid, req in grp.items()
            if req_uid in user_ids or req.get("target") in user_ids
        ]
        
        if not to_cancel:
            return None
        
        # 取消请求并返还次数
        for req_uid in to_cancel:
            rec_lim = grp_limit.get(req_uid, {"date": "", "count": 0})
            if rec_lim.get("date") == today and rec_lim.get("count", 0) > 0:
                rec_lim["count"] = max(0, rec_lim["count"] - 1)
                grp_limit[req_uid] = rec_lim
            del grp[req_uid]
        
        save_swap_requests()
        save_records()
        
        return f"已自动取消 {len(to_cancel)} 条相关的交换请求并返还次数~"

    async def terminate(self):
        """插件卸载时清理资源"""
        global config_locks, records, swap_requests, ntr_statuses
        
        # 清理群组配置锁
        config_locks.clear()
        
        # 清理全局数据
        records.clear()
        swap_requests.clear()
        ntr_statuses.clear()
