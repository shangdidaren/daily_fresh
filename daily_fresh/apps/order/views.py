from django.shortcuts import render, redirect
from datetime import datetime
# Create your views here.
from django.views.generic import View
from django.urls import reverse

from user.models import Address
from goods.models import GoodsSKU
from order.models import OrderInfo, OrderGoods
from django_redis import get_redis_connection

from utils.mixin import LoginRequiredMixin
from django.http import JsonResponse
from django.db import transaction  # mysql 事务


class OrderPlaceView(LoginRequiredMixin, View):
    '''提交订单'''

    def post(self, request):
        user = request.user
        # 获取
        sku_ids = request.POST.getlist('sku_ids')
        # 校验
        if not sku_ids:
            # 跳到购物车
            return redirect(reverse('cart:show'))
        # 遍历sku_ids ,获取选中的商品
        con = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        skus = []
        total_count = 0  # 总数
        total_price = 0     # 总价格
        for sku_id in sku_ids:
            sku = GoodsSKU.objects.get(id=sku_id)
            count = con.hget(cart_key, sku_id)
            count = int(count)
            # 计算商品的小计
            amount = sku.price * count
            # 动态增加属性，保存数量
            sku.count = count
            sku.amount = amount
            skus.append(sku)
            total_count += count
            total_price += amount

        # 运费，属于一个子系统，用于计算运费
        trans_price = 10

        # 实付款
        total_pay = total_price + trans_price
        addrs = Address.objects.filter(user=user)

        # 得到的sku_ids是列表形式的，所以改一下形式为字符串
        sku_ids = ','.join(sku_ids)

        # 组织下文
        context = {
            'skus': skus,
            'total_price': total_price,
            'total_count': total_count,
            'total_pay': total_pay,
            'addrs': addrs,
            'trans_price': trans_price,

            'sku_ids': sku_ids
        }

        # 使用模板
        return render(request, 'place_order.html', context)


# msyql事务
# 高并发
# 支付宝支付
class OrderCommitView(View):
    '''创建订单'''
    @transaction.atomic
    def post(self, request):
        '''地址id，支付方式pay_method，商品id的字符串sku_ids'''
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res': 0, 'errmsg': "用户未登录"})

        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        # 校验参数
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': "参数不完整"})
        # 支付方式

        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg': "非法的支付方式"})

        # 地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': "地址非法"})

        # todo 创建订单的核心业务
        # 组织参数 order_id:time+user
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        # 运费
        transit_price = 10
        # 总数目和总金额
        total_count = 0
        total_price = 0

        # 设置一个保存点
        save_id = transaction.savepoint()
        try:
            # todo 向df_order_info 表中，添加一条记录
            order = OrderInfo.objects.create(
                order_id=order_id,
                user=user,
                addr=addr,
                pay_method=pay_method,
                total_count=total_count,
                total_price=total_price,
                transit_price=transit_price)
            # todo 订单商品表的添加数据，用户订单里面有多少商品添加几条记录
            con = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            sku_ids = str(sku_ids).split(',')
            for sku_id in sku_ids:
                # 获取商品的信息
                try:
                    # 悲观锁  objects.select_for_update()
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                except BaseException:
                    transaction.savepoint_rollback(save_id)  # 情况不对马上回滚
                    return JsonResponse({'res': 4, 'errmsg': "不存在的商品"})
                # 从redis中获取用户索要购买的商品的数目
                count = int(con.hget(cart_key, sku_id))
                # 判断商品的库存，因为当订单创建完成后库存才会减少，而另一人比你快一步
                if int(count) > sku.stock:
                    transaction.savepoint_rollback(save_id)  # 情况不对再次回滚
                    return JsonResponse({'res': 6, 'errmsg': '商品库存不足'})

                # todo 向表中添加记录
                OrderGoods.objects.create(order=order, sku=sku, count=count,
                                          price=sku.price)
                # todo 更新商品的库存和销量
                sku.stock -= int(count)
                sku.sales += int(count)
                sku.save()

                #  累加计算商品的总数目和总价格
                amount = sku.price * int(count)
                total_price += amount
                total_count += count
                print(total_price)
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            print(e)
            transaction.savepoint_rollback(save_id)  # 情况不对又回滚
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})
            # todo 更新订单信息表中的总数量和总价格 , 之前写的是0
        # 没有发生异常提交
        transaction.savepoint_commit(save_id)
        # 删除用户在购物车的记录
        con.hdel(cart_key, *sku_ids)  # 执行了sku_ids长度次的操作，每次都是列表中的值，排队执行。
        return JsonResponse({'res': 5, 'message': '创建成功'})


class OrderPayView(View):
    '''订单支付'''

    def post(self, request):
        # 用户是否登陆
        user = request.user
        if not user:
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        # 接受参数
        order_id = request.POST.get('order_id')
        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的订单id'})

        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '无效的订单'})

        # 使用python SDK接口
        from django.conf import settings
        import os
        from alipay import AliPay
        app_private_key = open("apps/order/app_private_key.pem").read()
        alipay_public_key = open("apps/order/alipay_public_key.pem").read()
        alipay = AliPay(
            appid="2016101400682606",
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_string=alipay_public_key,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )

        # 调用支付接口
        subject = '天天'
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,
            total_amount=str(order.total_price + order.transit_price),
            # 因为我们的total_coun为DecimalField类型，不能被序列化，所以转换为str
            subject=subject,
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )
        # 跳转到https://openapi.alipaydev.com/gateway.do? + order_string
        # 返回应答
        pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
        return JsonResponse({'res': 3, 'pay_url': pay_url})


# 订单的检查
class CheckPayView(View):
    def post(self, request):
        '''查询支付结果'''
        # 用户是否登陆
        user = request.user
        if not user:
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        # 接受参数
        order_id = request.POST.get('order_id')
        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的订单id'})
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '只支持支付宝支付'})

        # 使用python SDK接口
        from django.conf import settings
        import os
        from alipay import AliPay
        app_private_key = open("apps/order/app_private_key.pem").read()
        alipay_public_key = open("apps/order/alipay_public_key.pem").read()
        alipay = AliPay(
            appid="2016101400682606",
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_string=alipay_public_key,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )
        # 上面部分和上面一样
        # 调用接口

        # response = {
        # "trade_no": "2017032121001004070200176844",                            # 支付宝交易号
        # "code": "10000",                                                   # 10000接口调用成功
        # "invoice_amount": "20.00",
        # "open_id": "20880072506750308812798160715407",
        # "fund_bill_list": [
        #     {
        #         "amount": "20.00",
        #         "fund_channel": "ALIPAYACCOUNT"
        #     }
        # ],
        # "buyer_logon_id": "csq***@sandbox.com",
        # "send_pay_date": "2017-03-21 13:29:17",
        # "receipt_amount": "20.00",
        # "out_trade_no": "out_trade_no15",
        # "buyer_pay_amount": "20.00",
        # "buyer_user_id": "2088102169481075",
        # "msg": "Success",
        # "point_amount": "0.00",
        # "trade_status": "TRADE_SUCCESS",                                          # 支付结果成功
        # "total_amount": "20.00"
        # }
        # 这个返回值是字典类型
        while True:
            response = alipay.api_alipay_trade_query(order_id)
            # 看看接口调用是否成功
            code = response.get('code')
            if code == '10000' and response.get(
                    'trade_status') == 'TRADE_SUCCESS':
                # 支付成功
                # 获取支付宝交易号
                # 更新订单状态
                # 返回结果
                trade_no = response.get('trade_no')

                order.order_status = 4  # 待评价
                print(order.order_status)
                order.trade_no = trade_no
                order.save()
                return JsonResponse({'res': 3, 'message': '支付成功'})
            elif code == '40004' or(code == '10000' and response.get('trade_status') == 'WAIT_BUYER_PAY'):
                # 等待卖家付款,要等一会
                import time
                time.sleep(5)
                continue
            else:
                # 支付出错，包括了时间超长
                return JsonResponse({'res': 4, 'errmsg': '支付失败'})


# 完成订单后，评论
class CommentView(View):
    def get(self, request, order_id):
        """展示评论页"""
        user = request.user

        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))

        # 需要根据状态码获取状态
        order.status_name = OrderInfo.ORDER_STATUS[order.order_status]

        # 根据订单id查询对应商品，计算小计金额,不能使用get
        order_skus = OrderGoods.objects.filter(order_id=order_id)
        for order_sku in order_skus:
            amount = order_sku.count * order_sku.price
            order_sku.amount = amount
        # 增加实例属性
        order.order_skus = order_skus

        context = {
            'order': order,
        }
        return render(request, 'order_comment.html', context)

    def post(self, request, order_id):
        """处理评论内容"""
        # 判断是否登录
        user = request.user

        # 判断order_id是否为空
        if not order_id:
            return redirect(reverse('user:order'))

        # 根据order_id查询当前登录用户订单
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))

        # 获取评论条数
        total_count = int(request.POST.get("total_count"))

        # 循环获取订单中商品的评论内容
        for i in range(1, total_count + 1):
            # 获取评论的商品的id
            sku_id = request.POST.get("sku_%d" % i)  # sku_1 sku_2
            # 获取评论的商品的内容
            content = request.POST.get(
                'content_%d' %
                i, '')  # comment_1 comment_2

            try:
                order_goods = OrderGoods.objects.get(
                    order=order, sku_id=sku_id)
            except OrderGoods.DoesNotExist:
                continue

            # 保存评论到订单商品表
            order_goods.comment = content
            order_goods.save()

        # 修改订单的状态为“已完成”
        order.order_status = 5  # 已完成
        order.save()
        # 1代表第一页的意思，不传会报错
        return redirect(reverse("user:order", kwargs={"page": 1}))
