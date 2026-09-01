"""帖子内容生成与上传图片预处理"""
import os
import random
import shutil
from datetime import datetime

from PIL import Image

from app.core.constants import (
    CITIES,
    COMPANIES,
    MAIN_TOPIC,
    OCCUPATIONS,
    SUB_TOPICS,
    TITLE_OPTIONS,
)


def generate_single_post_content() -> str:
    """生成单条符合要求的发帖内容（校友集结号模板）"""
    city = random.choice(CITIES)
    occupation = random.choice(OCCUPATIONS)
    company = random.choice(COMPANIES)
    sub_topic = random.choice(SUB_TOPICS)

    templates = [
        f"""毕业第2年了，时间过得真快！还记得散伙饭那晚，大家喝得微醺，互相说着"以后常联系"，结果微信群渐渐安静了。但芯泉子还在，我们的情谊还在。

现在「校友集结号」在芯泉子吹响，给了我们重新连接的机会。我在{city}，目前在一家{company}担任{occupation}。虽然工作忙碌，但时常会想起在芯泉子的日子。

你呢？现在在哪座城市？从事什么工作？生活怎么样？

{MAIN_TOPIC} {sub_topic}""",

        f"""又到了毕业季，不禁想起2年前我们的毕业典礼。散伙饭上，辅导员说"芯泉子永远是你们的家"，当时还没太在意，现在深有体会。

通过「校友集结号」活动，我看到了很多熟悉的名字。我在{city}做{occupation}，就职于{company}。虽然远离校园，但芯泉子的精神一直伴随着我。

老同学们，你们现在怎么样？来「校友集结号」报个到吧！

{MAIN_TOPIC} {sub_topic}""",

        f"""毕业第2年，我从一个青涩的毕业生变成了现在的{occupation}。在{city}的{company}工作，每天都有新的挑战。

还记得毕业那天，我们说好要"常回家看看"，结果忙碌的生活让联系变少了。感谢「校友集结号」活动，让我们有机会重新聚在一起。

说说你的现状吧，让老同学们知道你在哪里，过得好不好。

{MAIN_TOPIC} #毕业第2年 {sub_topic}""",

        f"""时间飞逝，转眼毕业2年了。那些在图书馆熬夜、在实验室通宵的日子还历历在目。现在我在{city}，是一名{occupation}，就职于{company}。

「校友集结号」的号角已经吹响，我在芯泉子等你们。分享你的近况，让我们一起重温校园时光。

你在哪座城市？现在做什么工作？有什么想对老同学说的？

{MAIN_TOPIC} {sub_topic}""",

        f"""2年时间，说长不长，说短不短。从校园到职场，从学生到{occupation}，我经历了很多成长。目前在{city}的{company}工作。

散伙饭上的约定，我还记得。虽然联系少了，但情谊没变。「校友集结号」让我们重新连接，分享各自的生活和成长。

来聊聊吧，毕业第2年的你，现在是什么样子？

{MAIN_TOPIC} #毕业第2年 {sub_topic}""",

        f"""毕业第2年，我来到了{city}，成为了一名{occupation}。在{company}工作的日子里，时常会想起在芯泉子的点点滴滴。

「校友集结号」活动让我看到了很多熟悉的名字。原来大家都在各自的领域努力着，真好。

说说你现在的生活吧，工作怎么样？生活顺心吗？有什么想分享的？

{MAIN_TOPIC} {sub_topic}""",

        f"""还记得2年前的今天，我们正在准备毕业答辩。现在，我在{city}做{occupation}，在{company}开启了职业生涯。

虽然工作忙碌，但总会抽时间回芯泉子看看。「校友集结号」活动给了我们一个很好的交流平台。

老同学们，你们现在都在哪里？从事什么工作？来「校友集结号」聊聊吧！

{MAIN_TOPIC} #毕业第2年 {sub_topic}""",

        f"""毕业第2年，我在{city}安了家。现在是一名{occupation}，就职于{company}。职场生活与校园截然不同，但芯泉子教给我的东西一直在用。

通过「校友集结号」，我看到了很多同学的近况。大家都在努力生活，努力成长。

你在哪里？现在过得怎么样？来分享你的故事吧！

{MAIN_TOPIC} {sub_topic}""",
    ]

    return random.choice(templates)


def random_title() -> str:
    """随机获取一个帖子标题"""
    return random.choice(TITLE_OPTIONS)


def pick_random_image(img_dir: str) -> str | None:
    """从图片库随机挑选一张图片，返回完整路径；无图片返回 None"""
    if not os.path.isdir(img_dir):
        return None
    candidates = [
        f for f in os.listdir(img_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"))
    ]
    if not candidates:
        return None
    return os.path.join(img_dir, random.choice(candidates))


def prepare_temp_upload_file(src_path: str, temp_dir: str, log=print) -> str:
    """创建本地临时副本（按当前时间重命名），并对图片随机裁切以增加真实性。

    返回：新文件的绝对路径
    """
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"上传文件不存在: {src_path}")

    os.makedirs(temp_dir, exist_ok=True)

    _, ext = os.path.splitext(src_path)
    new_name = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3] + ext
    temp_path = os.path.join(temp_dir, new_name)

    # 复制文件（保留元数据，更像真人文件）
    shutil.copy2(src_path, temp_path)

    # 对图片进行随机裁切
    try:
        with Image.open(temp_path) as img:
            width, height = img.size
            # 随机裁切比例：原图的80%到95%
            crop_ratio = random.uniform(0.8, 0.95)
            crop_width = int(width * crop_ratio)
            crop_height = int(height * crop_ratio)

            left = random.randint(0, width - crop_width)
            top = random.randint(0, height - crop_height)

            cropped_img = img.crop((left, top, left + crop_width, top + crop_height))
            cropped_img.save(temp_path)
            log(f"图片已随机裁切: 原尺寸({width}x{height}) -> 裁切尺寸({crop_width}x{crop_height})")
    except Exception as e:
        log(f"图片裁切失败，使用原文件: {str(e)}")

    return os.path.abspath(temp_path)


def clean_temp_upload_dir(temp_dir: str, log=print) -> None:
    """清空临时上传目录"""
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            log(f"已清空临时上传文件夹: {temp_dir}")
    except Exception as e:
        log(f"清空临时上传文件夹时出错: {str(e)}")
