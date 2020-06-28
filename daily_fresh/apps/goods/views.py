from django.shortcuts import render, redirect
from django.urls import reverse
from django_redis import get_redis_connection
from django.views.generic import View
from .models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner
from django.core.cache import cache

from .models import GoodsSKU
from order.models import OrderGoods
from django.core.paginator import Paginator


class IndexView(View):
    def get(self, request):
        # 先看缓存中有没有数据
        context = cache.get('index_page_data')
        if context is None:
            # 缓存为空设置缓存
            print('设置缓存')
            # 获取种类
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

            # 设置缓存
            context = {
                'types': types,
                'goods_banners': goods_banners,
                'promotion_banners': promotion_banners,
            }
            cache.set('index_page_data', context, 3600)  # key value timeout

        # 获取购物车中商品的数目
        user = request.user

        cart_count = 0
        if user.is_authenticated:
            con = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = con.hlen(cart_key)

        context['cart_count'] = cart_count
        from daily_fresh.settings import BASE_DIR, sys
        # print(sys)
        return render(request, 'index.html', context)


#  /goods/商品id
class DetailView(View):

    def get(self, request, goods_id):
        '''详情页'''
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            return redirect(reverse('goods:index'))

        # 获取商品的分类信息
        types = GoodsType.objects.all()
        # 评论信息
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='')

        # 新品的信息
        new_skus = GoodsSKU.objects.filter(
            type=sku.type).order_by('-create_time')[:2]

        # 获取跟此商品属于同一商品的其他规格
        same_spu_skus = GoodsSKU.objects.filter(
            goods=sku.goods).exclude(
            id=goods_id)  # 不包含自己

        # 获取购物车中商品的数目
        user = request.user

        cart_count = 0
        if user.is_authenticated:
            con = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = con.hlen(cart_key)

            # 添加历史浏览记录
            # 如果用户访问了之前访问商品，要先把之前的删除，再添加
            con = get_redis_connection('default')
            history_key = 'history_%d' % user.id
            con.lrem(history_key, 0, goods_id)
            # 把goods_id插入到左侧
            con.lpush(history_key, goods_id)
            # 只保存用户最新浏览的五条信息
            con.ltrim(history_key, 0, 4)  # ltrim  裁剪
        sku_orders = OrderGoods.objects.filter(sku=sku)
        context = {
            'sku': sku,
            'types': types,
            'new_skus': new_skus,
            'cart_count': cart_count,
            'same_spu_skus': same_spu_skus,
            'sku_orders': sku_orders
        }
        return render(request, 'detail.html', context)


# 种类id  页码  排序的方式
# /list/种类id/页码/
class ListView(View):

    def get(self, request, type_id, page):
        '''显示列表页'''

        # 先获取种类信息
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            return redirect(reverse('goods:index'))

        types = GoodsType.objects.all()

        # 获取排序的方式
        # sort = default ，按照默认id排序
        # sort = price ,按照商品的价格排序
        # sort = hot ,按照商品的销量排序
        sort = request.GET.get('sort')

        if sort == 'price':
            skus = GoodsSKU.objects.filter(type=type).order_by('price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_by(('-sales'))
        else:
            # 其他情况sort = 'default',防止地址栏的sort = None 比较不美观
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=type).order_by('-id')

        # 对数据进行分页
        paginator = Paginator(skus, 4)
        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1
        if page > paginator.num_pages:
            page = paginator.num_pages
        # 获取到了page页的Paginator对象
        skus_page = paginator.page(page)

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

        # 新品的信息
        new_skus = GoodsSKU.objects.filter(
            type=type).order_by('-create_time')[:2]

        # 购物车数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            con = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = con.hlen(cart_key)
        context = {
            'type': type,
            'types': types,
            'skus_page': skus_page,
            'new_skus': new_skus,
            'cart_count': cart_count,
            'sort': sort,  # 不穿过去，在列表页跳转后sort方式又变回默认了。也就是说你没办法按照同一种排序方式浏览到第二页。
            'pages': pages,
        }

        return render(request, 'list.html', context)
