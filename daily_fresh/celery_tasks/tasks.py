import os
# import django
# # os.environ.setdefault('DJANGO_SETTINGS_MODULE','dailyfresh.settings')
# # django.setup()

# 在worker端，先启动django环境，否则无法正常的导入类goods下的。
from django.http import request
from django.shortcuts import render
from django.template import loader,RequestContext

# 使用celery
from celery import Celery
from django.conf import settings
from django.core.mail import send_mail

from goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner
from django_redis import get_redis_connection
# 创建一个对象
broker = 'redis://47.100.179.209:6379/8'
backend = 'redis://47.100.179.209:6379/0'
# backend = 'redis://172.17.1.197:6379/0'
app = Celery('celery_tasks.tasks', broker=broker)

# 第一个参数随便 ，一般为路径
# 定义任务函数
@app.task
def send_register_active_email(to_email, username, token):
    subject = '主题'
    message = ''
    html_message = '<h1>%s, 欢迎您成为天天生鲜注册会员' \
                   '</h1>请点击下面链接激活您的账户<br/>' \
                   '<a href="http://127.0.0.1:8000/user/active/%s">' \
                   'http://127.0.0.1:8000/user/active/%s' \
                   '</a>' % (username, token, token)
    sender = settings.EMAIL_FROM
    receiver = [to_email]

    send_mail(
        subject,
        message,
        sender,
        receiver,
        html_message=html_message)
@app.task
def generate_static_index_html():
    types = GoodsType.objects.all()

    # 获取轮播
    goods_banners = IndexGoodsBanner.objects.all().order_by('index')

    # 获取首页的促销活动信息
    promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

    # 获取首页分类商品展示信息
    for type in types:
        # 图片种类
        image_banners = IndexTypeGoodsBanner.objects.filter(
            type=type, display_type=1).order_by('index')
        # 文字种类
        title_banners = IndexTypeGoodsBanner.objects.filter(
            type=type, display_type=0).order_by('index')
        # 动态增加属性
        type.image_banners = image_banners
        type.title_banners = title_banners

    context = {
        'types': types,
        'goods_banners': goods_banners,
        'promotion_banners': promotion_banners,
    }
    # 使用模板
    # 加载模板文件
    temp = loader.get_template('static_index.html')
    # 定义模板上下文
    # context = RequestContext(request,context)
    # 模板渲染
    static_index_html = temp.render(context)
    # 生成首页对应的静态文件
    save_path = os.path.join(settings.BASE_DIR, 'static/index.html')
    with open(save_path,'w') as f:
        f.write(static_index_html)
