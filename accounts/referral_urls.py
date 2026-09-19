from django.urls import path
from .views import ReferralRootView, ReferralStatsView, ReferralTreeView

urlpatterns = [
    path('<int:user_id>/tree/', ReferralTreeView.as_view(), name='referral-tree'),
    path('<int:user_id>/root/', ReferralRootView.as_view(), name='referral-root'),
    path('<int:user_id>/stats/', ReferralStatsView.as_view(), name='referral-stats'),
]
