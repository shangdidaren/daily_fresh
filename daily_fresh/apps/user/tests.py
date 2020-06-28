from django.test import TestCase
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','daily_fresh.settings')
django.setup()

# Create your tests here.
# from django.contrib.auth.hashers import make_password
#
# password = make_password('123456')
#
# print(password)
#
#
# text = r"[\w!#$%&'*+/=?^_`{|}~-]+(?:\.[\w!#$%&'*+/=?^_`{|}~-]+)*@(?:[\w](?:[\w-]*[\w])?\.)+[\w](?:[\w-]*[\w])?"
# import re
#
# email = 'fhaklj@345.com'
# email2 = '123ert.email@@163.com.cn.qq'
#
# if re.match(text,email2):
#     print("True")
# else :
#     print("False")

from django.core.cache import cache

print(cache.get('index_page_data'))