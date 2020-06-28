from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth import authenticate, login, logout  # django认证

from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.conf import settings
from django.urls import reverse

from goods.models import GoodsSKU
from order.models import OrderInfo, OrderGoods
from .models import User, Address

from django.views.generic import View
from utils.mixin import LoginRequiredMixin

from itsdangerous import TimedJSONWebSignatureSerializer as Serializer  # 用来签名
from itsdangerous import SignatureExpired  # 异常处理

from django.core.paginator import Paginator
from celery_tasks.tasks import send_register_active_email
from django.core.mail import send_mail  # 发邮件
# Create your views here.
import re


def log_out(request):
    logout(request)
    return redirect(reverse('user:login'))


class RegisterView(View):
    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        ''' 注册的处理 '''
        # 接受数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 数据校验
        if not all([username, password, email]):  # all中所有都为真返回真
            # 数据不完整
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        if not re.match(
            r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$',
                email):
            return render(request, 'register.html', {'errmsg': '邮箱不正确'})
        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '协议同意'})
        # 业务处理： 注册

        # 首先校验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 不存在
            user = None
        if user:
            return render(request, 'register.html', {'errmsg': '用户名已存在'})
        password = make_password(password)
        user = User.objects.create(
            username=username,
            email=email,
            password=password)
        user.is_active = 0
        user.save()

        # 发送激活邮件，包含激活链接 ：http:127.0.0.1:8000/user/active/加密的身份信息
        # 激活链接中需要包含用户的身份信息,并且把身份信息加密
        # 返回
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {"confirm": user.id}
        token = serializer.dumps(info).decode()
        # 发邮件
        # subject = '主题'
        # message = ''
        # html_message = '<h1>%s, 欢迎您成为天天生鲜注册会员' \
        #     '</h1>请点击下面链接激活您的账户<br/>' \
        #     '<a href="http://127.0.0.1:8000/user/active/%s">' \
        #     'http://127.0.0.1:8000/user/active/%s' \
        #     '</a>' % (username, token, token)
        # sender = settings.EMAIL_FROM
        # receiver = [email]
        #
        # send_mail(subject, message, sender, receiver,html_message=html_message)
        # 让celery帮忙发
        send_register_active_email.delay(email, username, token)
        return redirect(reverse('goods:index'))


class ActiveView(View):
    def get(self, request, token):
        # 获取
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            user_id = info["confirm"]
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            # 跳转到登陆页面
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            # 激活链接过期
            return HttpResponse('激活链接已经失效')


class LoginView(View):
    def get(self, request):
        if 'username' in request.COOKIES:     # 如果这个字段在COOKIE中，就赋值为username
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        # 将变量username和checked的传入前端页面。控制记住用户名的功能
        return render(request, 'login.html', locals())

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        if not all([username, password]):
            return render(request, 'login.html', {"errmsg": '数据不完整'})

        user = authenticate(
            username=username,
            password=password)  # 认证成功返回对象， 否则返回None

        if user is not None:
            if user.is_active:
                login(request, user)  # 记录登陆状态
                request.session.set_expiry(0)
                # logout(request)
                next_url = request.GET.get('next', reverse('goods:index'))
                # print(next_url)
                # 默认跳转到goods：index
                # print(reverse('goods:index')) reverse的值是个字符串
                # 先不返回，我们先接 一下
                response = redirect(next_url)
                rem = request.POST.get('remember')
                if rem == 'on':
                    response.set_cookie(
                        'username', username, max_age=7 * 24 * 3600)
                else:
                    response.delete_cookie('username')
                return response
            else:
                return render(request, 'login.html', {'errmsg': "用户未激活"})
        else:
            return render(request, 'login.html', {'errmsg': "用户名或者密码错误"})


# /user
class UserInfoView(LoginRequiredMixin, View):
    '''用户信息'''

    def get(self, request):

        # 获取用户信息
        user = request.user
        address = Address.objects.get_default_address(user)

        # 获取历史浏览记录
        # from redis import StrictRedis
        # StrictRedis(host='47.100.179.209',port=6379, db=2)

        from django_redis import get_redis_connection
        con = get_redis_connection("default")  # 就是StrictRedis类型的
        history_key = 'history_%d' % user.id
        # 获取用户最新浏览的五个商品
        sku_ids = con.lrange(history_key, 0, 4)  # 获取商品ids
        # 从数据库中查询用户浏览的商品的具体信息
        # GoodsSKU.objects.filter(id__in=sku_ids).order  但是这样查询不是顺序的
        # 所以按照顺序，一个一个查
        goods_li = []
        for id in sku_ids:
            goods_li.append(GoodsSKU.objects.get(id=id))
        return render(request, 'user_center_info.html', {'page': 'user',
                                                         'address': address,
                                                         'goods_li': goods_li})


# /user/order
class UserOrderView(LoginRequiredMixin, View):
    '''用户信息'''

    def get(self, request, page):
        user = request.user
        # from django_redis
        orders = OrderInfo.objects.filter(user=user)
        # 获取订单商品信息
        for order in orders:
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)
            # 遍历 order_skus 计算交际
            for order_sku in order_skus:
                amount = order_sku.count * order_sku.price
                # 动态增加属性
                order_sku.amount = amount
            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
            # 动态增加属性
            order.order_skus = order_skus

        # 然后对orders进行分页显示
        paginator = Paginator(orders, 2)

        try:
            page = int(page)
        except Exception as e:
            page = 1
        if page > paginator.num_pages:
            page = paginator.num_pages
            # 获取到了page页的Paginator对象
        order_page = paginator.page(page)

        # 对页码进行控制
        # 1. 页码总数小于5，显示所有
        # 2. 当前页是前三页，显示1-5
        # 3. 当前页是后3页，显示后5页
        # 4. 其他，显示当前的前两页和后两页和当前页

        num_pages = paginator.num_pages

        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        # 组织上下文
        context = {
            'order_page': order_page,
            'pages': pages,
            'page': 'order'
        }
        return render(request, 'user_center_order.html', context)


# /user/address
class AddressView(LoginRequiredMixin, View):
    '''用户信息'''

    def get(self, request):
        user = request.user

        address = Address.objects.get_default_address(user)

        return render(request, 'user_center_site.html', {'page': 'address',
                                                         'address': address})

    def post(self, request):
        # 地址添加
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        # 业务处理：地址添加
        # 如果用户没存在默认地址，则添加的地址作为默认收获地址
        user = request.user

        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     address = None  # 不存在默认地址
        address = Address.objects.get_default_address(user)
        # 将上面方法在类中定义了。
        if address:
            is_default = False
        else:
            is_default = True

        # 数据校验
        if not all([receiver, addr, phone]):
            return render(request, 'user_center_site.html',
                          {'page': 'address',
                           'address': address,
                           'errmsg': '数据不完整'})

        # 校验手机号
        if not re.match(r'^1([3-8][0-9]|5[189]|8[6789])[0-9]{8}$', phone):
            return render(request, 'user_center_site.html',
                          {'page': 'address',
                           'address': address,
                           'errmsg': '手机号格式不合法'})

        # 添加
        Address.objects.create(user=user,
                               receiver=receiver,
                               addr=addr,
                               zip_code=zip_code,
                               phone=phone,
                               is_default=is_default)

        # 返回应答
        return redirect(reverse('user:address'))  # get的请求方式
