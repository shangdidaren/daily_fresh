from django.conf.urls import url
from django.urls import path
from . views import RegisterView, ActiveView, LoginView, UserInfoView, UserOrderView, AddressView
from .views import log_out
from django.contrib.auth.decorators import login_required

app_name = 'user'
urlpatterns = [

    # url(r'^register$', views.register, name='register'),
    # url(r'^register_handle$', views.register_handle, name='register_handle')
    # url(r'^active/(?P<token>.*)$', views.ActiveView.as_view(), name='active'),

    url(r'^register$', RegisterView.as_view(), name='register'),
    path('active/<token>', ActiveView.as_view(), name='active'),
    # url(r'^login$', LoginView.as_view(), name='login'),
    path('login', LoginView.as_view(), name='login'),
    path('logout',log_out, name='logout'),
    path('', UserInfoView.as_view(), name='user'),
    path('order/<int:page>', UserOrderView.as_view(), name='order'),
    path('address', AddressView.as_view(), name='address'),

]
