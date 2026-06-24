import random
import time
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import At, Plain
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

@register("astrbot_plugin_qq_group_inspection", "CarefreeSongs712", "AstrBot QQ进群问答审核插件", "1.0.0")
class MyPlugin(Star):
    problems = []

    bot = None

    processing = False
    latest_qqid = 0
    latest_nickname = ""
    latest_answer_time = 0
    answer = ""
    wrong_times = 0

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        temp_problems = config.get("problems", [])
        for t in temp_problems:
            t1,t2 = t.split("|")
            t1,t2 = t1.strip(),t2.strip()
            self.problems.append((t1,t2))

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @filter.command("helloworld")
    async def helloworld(self, event: AstrMessageEvent):
        """这是一个 hello world 指令""" # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        user_name = event.get_sender_name()
        message_str = event.message_str # 用户发的纯文本消息字符串
        message_chain = event.get_messages() # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!") # 发送一条纯文本消息

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""

    
    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def event_monitoring(self, event: AiocqhttpMessageEvent):
        """监听进群/退群事件"""
        raw = getattr(event.message_obj, "raw_message", None)
        if not isinstance(raw, dict):
            return

        gid: str = str(raw.get("group_id", ""))
        client = event.bot
        uid: str = str(raw.get("user_id", ""))

        #if(gid != "1023130726"):
        #    return

        self.bot = event.bot

        if raw.get("notice_type") == "group_increase" and uid != event.get_self_id():
            if(self.processing):
                await event.bot.set_group_kick(
                    group_id=int(event.get_group_id()),
                    user_id=int(self.latest_qqid),
                    reject_add_request=False,
                )

            # 进群欢迎
            nickname = await self.get_nickname(event, uid)
            t = random.choice(self.problems)
            problem = t[0]
            answer = t[1]

            chain = [At(qq=uid), Plain(text=f"请完成入群验证：\n{problem}\n验证机会 3 次\n时长 5 分钟\n[tip:你只需发送结果,不需多余文字]")]
            await event.send(event.chain_result(chain))


            self.processing = True
            self.latest_qqid = uid
            self.latest_nickname = nickname
            self.latest_answer_time = time.time()
            self.answer = answer
            self.wrong_times = 0


            # welcome = f"@{nickname} 新人进群默认禁言10分钟，请仔细阅读Q群管家发送的本群注意事项。"
            # await event.send(event.plain_result(welcome))
            
            # 进群禁言
            if False:
                try:
                    await client.set_group_ban(
                        group_id=int(gid),
                        user_id=int(uid),
                        duration=600,
                    )
                except Exception:
                    pass

    @filter.event_message_type(filter.EventMessageType.ALL)

    async def on_message(self, event: AstrMessageEvent):
        logger.debug(f"收到消息: {event.message_str}")
        if(self.processing):
            if(time.time() - self.latest_answer_time > 300):
                await event.send(event.plain_result(f"@{self.latest_nickname} 验证超时，已被移出群聊"))
                await self.bot.set_group_kick(
                    group_id=int(event.get_group_id()),
                    user_id=int(self.latest_qqid),
                    reject_add_request=False,
                )
                self.processing = False
                return

        if(event.get_sender_id() == self.latest_qqid and event.message_str != "" and self.processing):
            if(event.message_str.strip() == self.answer):
                await event.send(event.plain_result(f"@{self.latest_nickname} 验证成功。"))
                self.processing = False
                await event.send(event.plain_result("新人进群默认禁言5分钟，请仔细阅读群公告的本群注意事项。"))
                try:
                    await self.bot.set_group_ban(
                        group_id=int(event.get_group_id()),
                        user_id=int(self.latest_qqid),
                        duration=300,
                    )
                except Exception:
                    pass
                
            else:
                self.wrong_times += 1
                if(self.wrong_times >= 3):
                    await event.send(event.plain_result(f"@{self.latest_nickname} 验证失败，已被移出群聊"))
                    await self.bot.set_group_kick(
                        group_id=int(event.get_group_id()),
                        user_id=int(self.latest_qqid),
                        reject_add_request=False,
                    )
                    self.processing = False
                else:
                    await self.bot.delete_msg(message_id=int(event.message_obj.message_id))
                    await event.send(event.plain_result(f"@{self.latest_nickname} 验证失败，请思考1分钟后，重新输入答案，剩余机会 {3 - self.wrong_times} 次"))
                    try:
                        await self.bot.set_group_ban(
                            group_id=int(event.get_group_id()),
                            user_id=int(self.latest_qqid),
                            duration=60,
                        )
                    except Exception:
                        pass
        
        
    async def get_nickname(self, event: AiocqhttpMessageEvent, user_id: int | str) -> str:
        """获取指定群友的群昵称或 Q 名，群接口失败/空结果自动降级到陌生人资料"""
        user_id = int(user_id)
        client = event.bot
        group_id = event.get_group_id()
        info = {}

        # 在群里就先试群资料，任何异常或空结果都跳过
        if group_id.isdigit():
            try:
                info = (
                    await client.get_group_member_info(
                        group_id=int(group_id), user_id=user_id
                    )
                    or {}
                )
            except Exception:
                pass

        # 群资料没拿到就降级到陌生人资料
        if not info:
            try:
                info = await client.get_stranger_info(user_id=user_id) or {}
            except Exception:
                pass

        # 依次取群名片、QQ 昵称、通用 nick，兜底数字 UID
        return info.get("card") or info.get("nickname") or info.get("nick") or str(user_id)
