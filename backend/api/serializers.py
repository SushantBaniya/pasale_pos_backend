from django.contrib.auth.models import User
from rest_framework import serializers
from api.models import AprioriRule, Billing, BillingItem, Counter, Employee, Order, OrderItem, OrderItemStatus, OrderStatus, StockAlert, Product, Party, Customer, Supplier, SupplierInfo, Expense, Skill, EmployeeSkill, Shift, EmployeeSchedule, Department, EmployeeStatus, PaymentTransaction, PaymentMethod, ExpenseCategory

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'


class PartySerializer(serializers.ModelSerializer):
    class Meta:
        model = Party
        fields = "__all__"

class PaymentTransactionSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source='party.name', read_only=True)

    payment_method = serializers.SlugRelatedField(
        slug_field='method_name', queryset=PaymentMethod.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = PaymentTransaction
        fields = "__all__"


class CustomerSerializer(serializers.ModelSerializer):
    payment_method = serializers.SlugRelatedField(
        slug_field='method_name', queryset=PaymentMethod.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Customer
        fields = "__all__"


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = "__all__"


class SupplierInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierInfo
        fields = ['id', 'name', 'email', 'phone_no', 'address',
                  'company_name',  'pan_number', 'open_balance']


class ExpenseSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(
        slug_field='name', queryset=ExpenseCategory.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Expense
        fields = ['id', 'user', 'amount', 'description',
                  'date', 'category', 'is_necessary', 'payment_method', 'expense_number']


class BillingItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='item.product_name', read_only=True)

    class Meta:
        model = BillingItem
        fields = "__all__"


class BillingSerializer(serializers.ModelSerializer):
    items = BillingItemSerializer(many=True, read_only=True)
    party = serializers.PrimaryKeyRelatedField(
        queryset=Party.objects.all(), required=False, allow_null=True
    )

    payment_method = serializers.SlugRelatedField(
        slug_field='method_name', queryset=PaymentMethod.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Billing
        fields = "__all__"

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if instance.party:
            rep['party'] = PartySerializer(instance.party).data
        return rep


class EmployeeSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(
        source='business_id.business_name', read_only=True)
    department = serializers.SlugRelatedField(
        slug_field='name', queryset=Department.objects.all(), required=False)
    status = serializers.SlugRelatedField(
        slug_field='name', queryset=EmployeeStatus.objects.all(), required=False)

    manager_name = serializers.CharField(
        source='manager.name', read_only=True, required=False)

    class Meta:
        model = Employee
        fields = ['id', 'name', 'email', 'phone_no', 'position', 'salary', 'hire_date',
                  'status', 'department', 'manager', 'manager_name', 'business_id', 'business_name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically scope the SlugRelatedField querysets to the current business_id
        # to prevent MultipleObjectsReturned when different businesses have the same department/status names.
        business_id = None
        if 'data' in kwargs and kwargs['data'] and 'business_id' in kwargs['data']:
            business_id = kwargs['data'].get('business_id')
        elif self.instance:
            if isinstance(self.instance, list):
                if len(self.instance) > 0:
                    business_id = getattr(self.instance[0], 'business_id_id', None)
            else:
                business_id = getattr(self.instance, 'business_id_id', None)
        
        if business_id:
            self.fields['department'].queryset = Department.objects.filter(business_id=business_id)


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name', 'description', 'business_id']


class EmployeeSkillSerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source='skill.name', read_only=True)
    employee_name = serializers.CharField(
        source='employee.name', read_only=True)

    class Meta:
        model = EmployeeSkill
        fields = ['id', 'employee', 'employee_name',
                  'skill', 'skill_name', 'proficiency_level']


class ShiftSerializer(serializers.ModelSerializer):
    required_skill_name = serializers.CharField(
        source='required_skill.name', read_only=True, allow_null=True)
    assigned_employee_name = serializers.CharField(
        source='assigned_employee.name', read_only=True, allow_null=True)

    class Meta:
        model = Shift
        fields = ['id', 'business_id', 'shift_date', 'start_time', 'end_time',
                  'required_skill', 'required_skill_name', 'required_employees',
                  'assigned_employee', 'assigned_employee_name', 'is_scheduled', 'created_at', 'updated_at']


class EmployeeScheduleSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(
        source='employee.name', read_only=True)

    class Meta:
        model = EmployeeSchedule
        fields = ['id', 'employee', 'employee_name',
                  'date', 'start_time', 'end_time']


class SchedulerRequestSerializer(serializers.Serializer):
    """Serializer for staff scheduling request"""
    business_id = serializers.IntegerField()
    shift_ids = serializers.ListField(child=serializers.IntegerField())
    max_hours_per_week = serializers.IntegerField(default=40, required=False)
    apply_schedule = serializers.BooleanField(default=False, required=False)

    weights = serializers.DictField(
        child=serializers.FloatField(),
        required=False,
        default={
            "availability": 0.30,
            "skill_match":  0.25,
            "fairness":     0.20,
            "skill_level":  0.15,
            "cost":         0.10,   
        }
    )


class SchedulerResponseSerializer(serializers.Serializer):
    """Serializer for scheduler response"""
    scheduled_count = serializers.IntegerField()
    unscheduled_count = serializers.IntegerField()
    total_shifts = serializers.IntegerField()
    success_rate = serializers.CharField()
    schedule_summary = serializers.DictField(required=False)


class OrderItemSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    status_id = serializers.PrimaryKeyRelatedField(
        source='status', queryset=OrderItemStatus.objects.all(), write_only=True, required=False, allow_null=True)
    product_name = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'order', 'product_id', 'product_name',
                  'quantity', 'unit_price', 'total_price', 'status', 'status_id']
        read_only_fields = ['status']

    def get_status(self, obj):
        return obj.status.name if obj.status else None

    def get_product_name(self, obj):
        return obj.product_id.product_name if obj.product_id else None


class OrderSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    status_id = serializers.PrimaryKeyRelatedField(
        source='order_status', queryset=OrderStatus.objects.all(), write_only=True, required=False, allow_null=True)
    order_date = serializers.DateTimeField(source='created_at', read_only=True)
    customer_name = serializers.SerializerMethodField()
    business_name = serializers.SerializerMethodField()
    items = OrderItemSerializer(many=True, read_only=True)
    counter_id = serializers.SerializerMethodField()
    counter_number = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'business_id', 'business_name', 'customer_id', 'customer_name', 'order_date',
                  'updated_at', 'created_at', 'total_amount', 'status', 'status_id', 'counter_id', 'counter_number', 'items']

        read_only_fields = ['status', 'customer_name',
                            'business_name', 'items', 'created_at', 'updated_at']

    def get_status(self, obj):
        return obj.order_status.name if obj.order_status else None

    def get_customer_name(self, obj):
        return obj.customer_id.name if obj.customer_id else None

    def get_business_name(self, obj):
        return obj.business_id.business_name if obj.business_id else None

    def get_counter_id(self, obj):
        return obj.counter.id if obj.counter else None

    def get_counter_number(self, obj):
        return obj.counter.counter_number if obj.counter else None


class CounterSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(
        source='business_id.business_name', read_only=True)

    class Meta:
        model = Counter
        fields = ['id', 'business_id', 'business_name',
                  'counter_number', 'location']
        read_only_fields = ['business_name']


class AprioriRuleSerializer(serializers.ModelSerializer):
    confidence_percent = serializers.SerializerMethodField()

    class Meta:
        model = AprioriRule
        fields = [
            'id',
            'antecedent',
            'consequent',
            'support',
            'confidence',
            'confidence_percent',
            'lift',
            'updated_at'
        ]

    def get_confidence_percent(self, obj):
        return f"{obj.confidence:.0%}"


class StockAlertSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.product_name')
    product_quantity = serializers.IntegerField(source='product.quantity')
    reorder_level = serializers.IntegerField(source='product.reorder_level')

    class Meta:
        model = StockAlert
        fields = [
            'id',
            'product_name',
            'product_quantity',
            'reorder_level',
            'message',
            'is_resolved',
            'created_at'
        ]


class ReorderSuggestionSerializer(serializers.Serializer):
    low_stock_product = serializers.CharField()
    current_quantity = serializers.IntegerField()
    reorder_level = serializers.IntegerField()
    also_reorder = serializers.ListField()

from .models import Reminder

class ReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reminder
        fields = '__all__'
