from django.urls import re_path

from .views import (
    APIInfoPage,
    AssetsInOrbitPage,
    XPubStatusPage,
    XpubRegistrationPage,
    XpubUnregistrationPage,
    TransactionListPage,
    TransactionDetailsPage,
    SendTransactionPage,
    ReceiveAddressPage,
    MultiBalanceHistoryPage,
    BalancePage,
    CreateUnsignedTransactionPage,
    SyncAccountBasedBalancesPage
)

from .metrics import (
    LatestBlockPage
)

from .network_fees import (
    NetworkFeesPage
)

urlpatterns = [
    re_path(r'^$', APIInfoPage.as_view()),
    re_path(r'^register$', XpubRegistrationPage.as_view()),
    re_path(r'^unregister$', XpubUnregistrationPage.as_view()),
    re_path(r'^send$', SendTransactionPage.as_view()),
    re_path(r'^receive$', ReceiveAddressPage.as_view()),
    re_path(r'^transactions$', TransactionListPage.as_view()),
    re_path(r'^transaction$', TransactionDetailsPage.as_view()),
    re_path(r'^balance/multihistory$', MultiBalanceHistoryPage.as_view()),
    re_path(r'^balance$', BalancePage.as_view()),
    re_path(r'^tools/create_unsigned_transaction$', CreateUnsignedTransactionPage.as_view()),
    re_path(r'^metrics/latest_block$', LatestBlockPage.as_view()),
    re_path(r'^metrics/assets_in_orbit$', AssetsInOrbitPage.as_view()),
    re_path(r'^xpubs$', XPubStatusPage.as_view()),
    re_path(r'^sync_account_based_balances$', SyncAccountBasedBalancesPage.as_view()),
    re_path(r'^network_fees$', NetworkFeesPage.as_view()),
]
