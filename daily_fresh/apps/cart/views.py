from django.http import JsonResponse
from django.shortcuts import render

# Create your views here.
from django.views.generic import View
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
from goods.models import GoodsSKU


class CartAddView(View):
    """购物车记录添加"""

    def post(self, request):

        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '请先登录'})

        # 接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 数据校验
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        # 校验添加的商品数量
        # noinspection PyBroadException
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        # 业务处理：添加购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 先尝试获取sku_id的值 -> hget cart_key 属性: cart_key[sku_id]
        # 如果sku_id在hash中不存在，hget返回None
        cart_count = conn.hget(cart_key, sku_id)
        if cart_count:
            # redis中存在该商品，进行数量累加
            count += int(cart_count)

        # 校验商品的库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品库存不足'})
        # 设置hash中sku_id对应的值
        # hset ->如sku_id存在,更新数据,如sku_id不存在，追加数据
        conn.hset(cart_key, sku_id, count)

        # 获取用户购物车中的条目数
        cart_count = conn.hlen(cart_key)

        # 返回应答
        return JsonResponse({'res': 5, 'cart_count': cart_count, 'message': '添加成功'})


class CartInfoView(LoginRequiredMixin, View):
    '''购物车结算页面'''

    def get(self, request):
        # 登陆的用户
        user = request.user

        # 获取购物车中商品的信息
        con = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 商品id  ：数量
        cart_dict = con.hgetall(cart_key)

        skus = []
        total_count = 0  # 总数目
        total_price = 0  # 总价格

        # 遍历这个字典
        for sku_id, count in cart_dict.items():
            # 根据id 获取商品的信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 计算小计
            amount = sku.price * int(count)
            # 动态的位sku增加属性
            sku.amount = amount
            sku.count = int(count)
            skus.append(sku)
            total_count += int(count)
            total_price += amount

        context = {
            'skus': skus,
            'total_count': total_count,
            'total_price': total_price,
        }
        return render(request, 'cart.html', context)


class CartUpdateView(View):
    '''响应前端发来的ajax请求，完成更新购物车的操作'''

    def post(self, request):
        '''购物车的操作就是对数据库cart—的操作，需要前端发来sku_id和count'''
        con = get_redis_connection('default')
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '请先登录'})

        # 接收数据 得到的就是一种商品的值，每次改变数量都会向这里来发送请求，走的是次数，而不是量
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 数据校验
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        # 校验添加的商品数量
        # noinspection PyBroadException
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        # 更新数据库
        cart_key = 'cart_%d' % user.id
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品数量不足'})
        con.hset(cart_key, sku_id, count)

        # 计算商品的总数
        total_count = 0
        vals = con.hvals(cart_key)  # 将cart_key中的value作为列表返回，相当于dic.values()
        for val in vals:
            total_count += int(val)  # 所有的value值加起来就是商品的总件数。
        # 返回应答
        return JsonResponse({'res': 5, 'message': '更新成功', 'total_count': total_count})
        # 这个


class DelCartView(View):
    def get(self, request):
        con = get_redis_connection('default')
        user = request.user
        cart_key = 'cart_%d' % user.id

        total_count = 0
        try:
            con.delete(cart_key)
            return render(request, 'cart.html', {'total_count': total_count})
        except:
            return render(request, 'cart.html', {'total_count': total_count})


class CartDelView(View):
    '''购物车记录的删除'''

    def post(self, request):
        # 判断用户是否登陆
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '请先登录'})
        # 接受参数
        sku_id = request.POST.get('sku_id')
        # 数据校验
        if not sku_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的商品id'})
        # 商品是否存在

        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': 's商品不存在'})
        # 删除购物车记录
        con = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        con.hdel(cart_key, sku_id)
        return JsonResponse({'res': 3, 'message': '删除成功'})
