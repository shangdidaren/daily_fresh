from django.contrib.auth.decorators import login_required


# python2
# class LoginRequiredMixin(object):
#     @classmethod
#     def as_view(cls, **initkwargs):
#         view = super(LoginRequiredMixin, cls).as_view(**initkwargs)
#         return login_required(view)


# python 3
class LoginRequiredMixin():
    @classmethod
    def as_view(cls):
        view = super().as_view()
        return login_required(view)
