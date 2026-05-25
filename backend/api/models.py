from decimal import Decimal
from django.contrib.auth.models import User
from django.db import models


class Business_Type(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Business_Status(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class EmployeeStatus(models.Model):
    name = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class OrderStatus(models.Model):
    name = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name


class OrderItemStatus(models.Model):
    name = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name


class Business(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='businesses')
    business_name = models.CharField(max_length=255)
    business_address = models.TextField(blank=True, null=True)
    business_email = models.EmailField(blank=True, null=True)
    business_phone_no = models.CharField(max_length=15, blank=True, null=True)
    business_type = models.ForeignKey(
        Business_Type, on_delete=models.CASCADE, related_name='businesses', blank=True, null=True)
    business_status = models.ForeignKey(
        Business_Status, on_delete=models.CASCADE, related_name='businesses', blank=True, null=True)
    reg_number = models.CharField(max_length=100, blank=True, null=True)
    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.business_name


class Department(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    business_id = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='departments', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Employee(models.Model):
    id = models.AutoField(primary_key=True)  # Explicit primary key
    business_id = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='employees', null=True, blank=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone_no = models.CharField(max_length=15, blank=True, null=True)
    position = models.CharField(max_length=100, blank=True, null=True)
    salary = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'))
    hire_date = models.DateField(null=True, blank=True)
    status = models.ForeignKey(
        EmployeeStatus, on_delete=models.SET_NULL, null=True, blank=True)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, related_name='employees', null=True, blank=True)
    manager = models.ForeignKey(
        'self', on_delete=models.SET_NULL, related_name='subordinates', null=True, blank=True)

    def __str__(self):
        return self.name


class EmployeeSchedule(models.Model):
    id = models.AutoField(primary_key=True)  # Explicit primary key
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='schedules')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.employee.name} - {self.date}"


class Category(models.Model):
    id = models.AutoField(primary_key=True)  # Explicit primary key
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    def __str__(self):
        return self.name


class PaymentMethod(models.Model):
    id = models.AutoField(primary_key=True)  # Explicit primary key
    method_name = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.method_name


class Product(models.Model):
    id = models.AutoField(primary_key=True)  # Explicit primary key
    product_name = models.CharField(max_length=100)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name='products')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    sku = models.CharField(max_length=50, null=True, blank=True)
    business_id = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='products', null=True, blank=True)
    quantity = models.PositiveIntegerField()
    reorder_level = models.PositiveIntegerField(default=10)
    is_low_stock = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    product_Img = models.ImageField(
        upload_to='products/', null=True, blank=True)
    is_created_at = models.DateTimeField(auto_now_add=True, null=True)
    is_updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.product_name

    def save(self, *args, **kwargs):
        # 1. Update status before saving
        self.is_low_stock = self.quantity <= self.reorder_level

        # 2. Save the product
        super().save(*args, **kwargs)

        # 3. Handle StockAlerts (without calling another .save() to avoid recursion)
        from api.models import StockAlert
        if self.is_low_stock and self.business_id:
            # Create an alert if it doesn't exist
            StockAlert.objects.get_or_create(
                product=self,
                business_id=self.business_id,
                is_resolved=False,
                defaults={
                    'message': f"Low Stock Alert: {self.product_name} only has {self.quantity} left!"
                }
            )
        elif not self.is_low_stock:
            # If stock is now above threshold, resolve any pending alerts
            StockAlert.objects.filter(
                product=self,
                is_resolved=False
            ).update(is_resolved=True)


class Party(models.Model):
    id = models.AutoField(primary_key=True)  # Explicit primary key
    business_id = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='parties', null=True, blank=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    phone_no = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    pan_number = models.CharField(max_length=20, blank=True, null=True)
    avatar = models.ImageField(upload_to='parties/', null=True, blank=True)
    open_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'))
    credit_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'))

    Category_type = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    is_updated_at = models.DateTimeField(auto_now=True)

   # meta class for ordering and plural name(settings)
    class Meta:
        verbose_name_plural = 'Parties'
        indexes = [
            models.Index(fields=['business_id', 'Category_type']),
        ]

    def __str__(self):
        return self.name if self.name else f"Party {self.id}"


class PaymentTransaction(models.Model):
    id = models.AutoField(primary_key=True)
    business_id = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='payment_transactions', null=True, blank=True)
    party = models.ForeignKey(
        Party, on_delete=models.CASCADE, related_name='payment_transactions')

    receipt_number = models.CharField(max_length=50, blank=True, null=True)
    is_manual_receipt = models.BooleanField(default=False)
    date = models.DateField()

    PAYMENT_TYPES = [
        ('payment_in', 'Payment In'),
        ('payment_out', 'Payment Out'),
    ]
    transaction_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.ForeignKey(
        PaymentMethod, on_delete=models.SET_NULL, null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='payments/', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.party.name} - {self.amount}"


class Customer(models.Model):
    id = models.AutoField(primary_key=True)  # Explicit primary key
    party = models.OneToOneField(
        Party, on_delete=models.CASCADE, related_name='Customer')
    business_id = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='customers', null=True, blank=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone_no = models.CharField(max_length=15, blank=True, null=True)
    Customer_code = models.CharField(max_length=50, unique=True, null=True)
    address = models.TextField(blank=True, null=True)
    # financial details
    open_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00)
    credit_limmit = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00)

    payment_method = models.ForeignKey(
        PaymentMethod, on_delete=models.SET_NULL, null=True, blank=True, related_name='customers')

    loyalty_points = models.IntegerField(default=0)
    # additional info
    referred_by = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Counter(models.Model):
    business_id = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='counters')
    counter_number = models.IntegerField(unique=True)
    location = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Counter {self.counter_number}"


class Order(models.Model):
    id = models.AutoField(primary_key=True)  # Explicit primary key
    customer_id = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name='orders', null=True, blank=True)
    business_id = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='orders', null=True, blank=True)
    counter = models.ForeignKey(
        Counter, on_delete=models.SET_NULL, related_name='orders', null=True, blank=True)
    order_status = models.ForeignKey(
        OrderStatus, on_delete=models.SET_NULL, null=True, blank=True)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order {self.id} - {self.order_status.name if self.order_status else 'No Status'}"


class OrderItem(models.Model):
    id = models.AutoField(primary_key=True)  # Explicit primary key
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='items')
    product_id = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='order_items')
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.ForeignKey(
        OrderItemStatus, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        """Auto-calculate total_price before saving"""
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Item {self.id} for Order {self.order.id}"


class Supplier(models.Model):
    id = models.AutoField(primary_key=True)  # Explicit primary key
    party = models.OneToOneField(
        Party, on_delete=models.CASCADE, related_name='Supplier')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    business_id = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='suppliers', null=True, blank=True)

    def __str__(self):
        return self.name


class SupplierInfo(models.Model):
    id = models.AutoField(primary_key=True)  # Explicit primary key
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name='supplier_infos')
    phone_no = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    pan_number = models.CharField(max_length=20, blank=True, null=True)
    # bank details
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    ifsc_code = models.CharField(max_length=20, blank=True, null=True)
    # balance info
    open_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00)
    credit_limmit = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00)

    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.supplier.name}"


class Expense(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='expenses')
    business_id = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='expenses', null=True, blank=True)
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True, null=True, db_column='remarks')
    date = models.DateField()
    is_necessary = models.BooleanField(default=True)
    expense_number = models.CharField(
        unique=True, max_length=50, blank=True, null=True, db_column='expense_no')
    payment_method = models.CharField(max_length=50, default='Cash')

    def __str__(self):
        return self.user.username


class Billing(models.Model):
    id = models.AutoField(primary_key=True)  # Explicit primary key
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='billings')
    business_id = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='billings', null=True, blank=True)
    order = models.OneToOneField(
        Order, on_delete=models.SET_NULL, related_name='billing', null=True, blank=True)

    # Invoice details
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_date = models.DateField(null=True, blank=True, db_index=True)
    due_date = models.DateField(null=True, blank=True)
    transaction_type = models.CharField(
        max_length=20, default='Sales', db_index=True)

    payment_method = models.ForeignKey(
        PaymentMethod, on_delete=models.SET_NULL, null=True)
    invoice_choices = [
        ('Paid', 'Paid'),
        ('Unpaid', 'Unpaid'),
        ('Pending', 'Pending'),
        ('Draft', 'Draft'),
    ]
    invoice_status = models.CharField(
        max_length=20, choices=invoice_choices, default='Draft', db_index=True)
    # Customer details
    party = models.ForeignKey(
        Party, on_delete=models.CASCADE, related_name='billings', null=True, blank=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    VAt_number = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    # Items and amounts

    # Summary
    notes = models.TextField(blank=True, null=True)
    paid_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00)
    due_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00)
    discount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    sub_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00)

    def calculate_totals(self):
        """Calculate subtotal from all invoice items"""
        self.sub_total = sum(item.total_price for item in self.items.all())
        self.total_amount = self.sub_total - self.discount + self.tax
        self.save()

    def save(self, *args, **kwargs):
        if self.invoice_status == 'Paid':
            self.paid_amount = self.total_amount
            self.due_amount = Decimal('0.00')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.user.username

    class Meta:
        indexes = [
            models.Index(
                fields=['business_id', 'invoice_date', 'transaction_type']),
        ]


class BillingItem(models.Model):
    id = models.AutoField(primary_key=True)  # Explicit primary key
    billing = models.ForeignKey(
        Billing, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='billing_items')
    quantity = models.PositiveIntegerField()
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    tax_percentage = models.DecimalField(
        max_digits=10, decimal_places=2, default=13.00)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        """Auto-calculate total_price before saving"""
        self.total_price = self.quantity * self.rate
        super().save(*args, **kwargs)
        self.billing.calculate_totals()

    def __str__(self):
        return f"Item {self.id} for Billing {self.billing.id}"


class ForgetPasswordOTP(models.Model):
    id = models.AutoField(primary_key=True)  # Explicit primary key
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='forget_password_otps')
    otp = models.CharField(max_length=6, null=True, blank=True)
    otp_created_at = models.DateTimeField(null=True, blank=True)
    is_verify = models.BooleanField(default=False)

    def __str__(self):
        return f"OTP for {self.user.username}"


class Skill(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    business_id = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='skills', null=True, blank=True)

    class Meta:
        unique_together = ('name', 'business_id')

    def __str__(self):
        return self.name


class EmployeeSkill(models.Model):
    id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='skills')
    skill = models.ForeignKey(
        Skill, on_delete=models.CASCADE, related_name='employees')
    proficiency_level = models.CharField(
        max_length=20, choices=[('Beginner', 'Beginner'), ('Intermediate', 'Intermediate'), ('Advanced', 'Advanced')], default='Beginner')

    class Meta:
        unique_together = ('employee', 'skill')

    def __str__(self):
        return f"{self.employee.name} - {self.skill.name}"


class Shift(models.Model):
    id = models.AutoField(primary_key=True)
    business_id = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='shifts')
    shift_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    required_skill = models.ForeignKey(
        Skill, on_delete=models.SET_NULL, null=True, blank=True, related_name='shifts')
    required_employees = models.PositiveIntegerField(default=1)
    assigned_employee = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_shifts')
    is_scheduled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['shift_date', 'start_time']

    def __str__(self):
        return f"Shift {self.id} - {self.shift_date} {self.start_time}-{self.end_time}"


class StockAlert(models.Model):
    business_id = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='stock_alerts')
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='stock_alerts')
    message = models.CharField(max_length=255)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['product'],
                condition=models.Q(is_resolved=False),
                name='unique_unresolved_stockalert_per_product',
            )
        ]

    def __str__(self):
        return f"Alert for {self.product.product_name} - {'Resolved' if self.is_resolved else 'Pending'}"


class AprioriRule(models.Model):
    business_id = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='apriori_rules'
    )
    antecedent = models.CharField(max_length=255)   # trigger product
    consequent = models.CharField(max_length=255)   # suggested product
    support = models.FloatField()
    confidence = models.FloatField()
    lift = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('business_id', 'antecedent', 'consequent')

    def __str__(self):
        return (
            f"{self.antecedent} → {self.consequent} "
            f"(conf: {self.confidence:.0%}, lift: {self.lift:.2f})"
        )


class Reminder(models.Model):
    id = models.AutoField(primary_key=True)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='reminders')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    due_date = models.DateTimeField()
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        indexes = [
            models.Index(fields=['business', 'due_date']),
        ]
