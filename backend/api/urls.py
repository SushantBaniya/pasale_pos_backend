from django.urls import path
from api.views import ReminderView, CounterView, EmployeeView, OrderView, ManualAssignView, OrderStatusView, SignupView, VerifySignupOtpView, ApiProductView, LoginView, ApiPartyView, ApiPaymentTransactionView, ApiExpenseView, ApiBillingView, ForgetPasswordView,VerifyForgetPasswordOtpView, ResetPasswordView, StaffSchedulerView, AssociationRulesView, ReorderSuggestionsView, StockAlertsView, ResolveAlertView, RetrainAprioriView, DepartmentView, SkillView, EmployeeSkillView, ShiftCRUDView
from api.views_reports import BusinessSummaryView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('signup/', SignupView.as_view(), name='user-register'),
    path('login/', LoginView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('verify-signup-otp/', VerifySignupOtpView.as_view(),
         name='verify-signup-otp'),
    

    path('products/b<int:business_id>/',
         ApiProductView.as_view(), name='ApiProductView'),
    path('products/b<int:business_id>/p<int:product_id>/',
         ApiProductView.as_view(), name='ApiProductView'),

    path('parties/b<int:business_id>/',
         ApiPartyView.as_view(), name='ApiPartyView'),
    path('parties/b<int:business_id>/p<int:party_id>/',
         ApiPartyView.as_view(), name='ApiPartyView'),

    path('payment-transactions/b<int:business_id>/',
         ApiPaymentTransactionView.as_view(), name='ApiPaymentTransactionView'),
    path('payment-transactions/b<int:business_id>/t<int:transaction_id>/',
         ApiPaymentTransactionView.as_view(), name='ApiPaymentTransactionView'),

    path('expenses/b<int:business_id>/',
         ApiExpenseView.as_view(), name='ApiExpenseView'),
    path('expenses/b<int:business_id>/e<int:expense_id>/',
         ApiExpenseView.as_view(), name='ApiExpenseView'),

    path('billing/b<int:business_id>/',
         ApiBillingView.as_view(), name='ApiBillingView'),
    path('billing/b<int:business_id>/b<int:billing_id>/',
         ApiBillingView.as_view(), name='ApiBillingView'),

    path('forget-password/', ForgetPasswordView.as_view(), name='forget-password'),
    path('verify-forget-password-otp/', VerifyForgetPasswordOtpView.as_view(),
         name='verify-forget-password-otp'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),

    path('employee/b<int:business_id>/',
         EmployeeView.as_view(), name='Employee-list-create'),
    path('employee/b<int:business_id>/e<int:employee_id>/',
         EmployeeView.as_view(), name='Employee-list-detail'),

    path('skills/b<int:business_id>/',
         SkillView.as_view(), name='skill-list-create'),
    path('skills/b<int:business_id>/s<int:skill_id>/',
         SkillView.as_view(), name='skill-detail'),

    path('employee-skills/b<int:business_id>/e<int:employee_id>/',
         EmployeeSkillView.as_view(), name='employee-skill-list-create'),
    path('employee-skills/b<int:business_id>/e<int:employee_id>/s<int:skill_id>/',
         EmployeeSkillView.as_view(), name='employee-skill-detail'),

    path('shifts/b<int:business_id>/',
         ShiftCRUDView.as_view(), name='shift-list-create'),
    path('shifts/b<int:business_id>/s<int:shift_id>/',
         ShiftCRUDView.as_view(), name='shift-detail'),

    path('departments/b<int:business_id>/',
         DepartmentView.as_view(), name='department-list-create'),

    path('scheduler/b<int:business_id>/',
         StaffSchedulerView.as_view(), name='scheduler-get-shifts'),
    path('scheduler/schedule/',
         StaffSchedulerView.as_view(), name='scheduler-run'),

    path('counters/b<int:business_id>/',
         CounterView.as_view(), name='counter-list-create'),
    path('counters/b<int:business_id>/c<int:counter_id>/',
         CounterView.as_view(), name='counter-detail'),

    path('orders/b<int:business_id>/',
         OrderView.as_view(), name='order-list-create'),
    path('orders/b<int:business_id>/c<int:customer_id>/',
         OrderView.as_view(), name='order-customer-list'),
    path('orders/b<int:business_id>/cntr<int:counter_id>/',
         OrderView.as_view(), name='order-counter-list'),
    path('orders/b<int:business_id>/o<int:order_id>/',
         OrderView.as_view(), name='order-detail'),
    path('order-statuses/',
         OrderStatusView.as_view(), name='order-status-list'),

    path(
        'inventory/rules/b<int:business_id>/',
        AssociationRulesView.as_view(),
        name='inventory-rules'
    ),
    path(
        'inventory/suggestions/b<int:business_id>/',
        ReorderSuggestionsView.as_view(),
        name='inventory-suggestions'
    ),
    path(
        'inventory/alerts/b<int:business_id>/',
        StockAlertsView.as_view(),
        name='inventory-alerts'
    ),
    path(
        'inventory/alerts/b<int:business_id>/<int:alert_id>/resolve/',
        ResolveAlertView.as_view(),
        name='inventory-alert-resolve'
    ),
    path(
        'inventory/retrain/b<int:business_id>/',
        RetrainAprioriView.as_view(),
        name='inventory-retrain'
    ),
    path(
        'reports/summary/b<int:business_id>/',
        BusinessSummaryView.as_view(),
        name='business-summary'
    ),

    path(
        'scheduler/shift/<int:shift_id>/assign/',
        ManualAssignView.as_view(),
        name='manual-assign'
    ),
    
    path('reminders/b<int:business_id>/', 
         ReminderView.as_view(), name='reminder-list-create'),
    path('reminders/b<int:business_id>/r<int:reminder_id>/', 
         ReminderView.as_view(), name='reminder-detail'),
]
