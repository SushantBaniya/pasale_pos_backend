# NamastePMS API Contract Documentation

**Version:** 1.0.0  
**Base URL:** `http://localhost:8000/api`  
**Content-Type:** `application/json`

---

## Table of Contents

1. [Authentication](#authentication)
   - [Signup](#signup)
   - [Verify Signup OTP](#verify-signup-otp)
   - [Login](#login)
   - [Verify Login OTP](#verify-login-otp)
   - [Forget Password](#forget-password)
   - [Verify Forget Password OTP](#verify-forget-password-otp)
   - [Reset Password](#reset-password)
   - [Refresh Token](#refresh-token)
2. [Products](#products)
   - [List Products](#list-products)
   - [Create Product](#create-product)
   - [Update Product](#update-product)
   - [Delete Product](#delete-product)
3. [Parties (Customers/Suppliers)](#parties)
   - [List Parties](#list-parties)
   - [Get Party by ID](#get-party-by-id)
   - [Create Party](#create-party)
   - [Update Party](#update-party)
   - [Delete Party](#delete-party)
4. [Expenses](#expenses)
   - [List Expenses](#list-expenses)
   - [Create Expense](#create-expense)
   - [Update Expense](#update-expense)
   - [Delete Expense](#delete-expense)
5. [Billing](#billing)
   - [List Billings](#list-billings)
   - [Create Billing](#create-billing)
   - [Update Billing](#update-billing)
   - [Delete Billing](#delete-billing)
6. [Error Codes](#error-codes)
7. [Data Models](#data-models)

---

## Authentication

All protected endpoints require a JWT Bearer token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

### Signup

Creates a new user account and sends an OTP to the provided email.

**Endpoint:** `POST /signup/`  
**Authentication:** None

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | Yes | Unique username |
| `email` | string | Yes | User's email address |
| `password` | string | Yes | User's password |
| `phone_no` | string | No | Phone number |
| `business_name` | string | No | Business name |

#### Example Request

```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "SecurePass123!",
  "phone_no": "+919876543210",
  "business_name": "John's Store"
}
```

#### Response

**Status:** `201 Created`

```json
{
  "message": "User created successfully. Please verify the OTP sent to your email."
}
```

---

### Verify Signup OTP

Verifies the OTP sent during signup to activate the user account.

**Endpoint:** `POST /verify-signup-otp/`  
**Authentication:** None

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | User's email address |
| `otp` | string | Yes | 6-digit OTP received via email |

#### Example Request

```json
{
  "email": "john@example.com",
  "otp": "123456"
}
```

#### Success Response

**Status:** `200 OK`

```json
{
  "message": "Signup OTP verified successfully!"
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `400 Bad Request` | `{"error": "OTP expired"}` |
| `400 Bad Request` | `{"error": "Invalid OTP"}` |
| `400 Bad Request` | `{"error": "No OTP found"}` |
| `404 Not Found` | `{"error": "User not found"}` |

---

### Login

Initiates login by sending an OTP to the user's email after verifying credentials.

**Endpoint:** `POST /login/`  
**Authentication:** None

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | User's email address |
| `password` | string | Yes | User's password |

#### Example Request

```json
{
  "email": "john@example.com",
  "password": "SecurePass123!"
}
```

#### Success Response

**Status:** `200 OK`

```json
{
  "message": "OTP sent to your email. Please verify to proceed."
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `401 Unauthorized` | `{"error": "Invalid credentials"}` |
| `404 Not Found` | `{"error": "User not found"}` |

---

### Verify Login OTP

Verifies the login OTP and returns JWT tokens upon success.

**Endpoint:** `POST /verify-login-otp/`  
**Authentication:** None

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | User's email address |
| `otp` | string | Yes | 6-digit OTP received via email |

#### Example Request

```json
{
  "email": "john@example.com",
  "otp": "123456"
}
```

#### Success Response

**Status:** `200 OK`

```json
{
  "message": "Login OTP verified successfully!",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `400 Bad Request` | `{"error": "OTP expired"}` |
| `400 Bad Request` | `{"error": "Invalid OTP"}` |
| `404 Not Found` | `{"error": "User not found"}` |

---

### Forget Password

Initiates password reset by sending an OTP to the user's email.

**Endpoint:** `POST /forget-password/`  
**Authentication:** None

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | User's email address |

#### Example Request

```json
{
  "email": "john@example.com"
}
```

#### Success Response

**Status:** `200 OK`

```json
{
  "message": "OTP sent to your email. Please verify to reset your password."
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `404 Not Found` | `{"error": "User not found"}` |

---

### Verify Forget Password OTP

Verifies the OTP for password reset.

**Endpoint:** `POST /verify-forget-password-otp/`  
**Authentication:** None

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | User's email address |
| `otp` | string | Yes | 6-digit OTP received via email |

#### Example Request

```json
{
  "email": "john@example.com",
  "otp": "123456"
}
```

#### Success Response

**Status:** `200 OK`

```json
{
  "message": "Forget Password OTP verified successfully!"
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `400 Bad Request` | `{"error": "OTP expired"}` |
| `400 Bad Request` | `{"error": "Invalid OTP"}` |
| `404 Not Found` | `{"error": "User not found"}` |

---

### Reset Password

Resets the user's password after OTP verification.

**Endpoint:** `POST /reset-password/`  
**Authentication:** None

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | User's email address |
| `new_password` | string | Yes | New password |

#### Example Request

```json
{
  "email": "john@example.com",
  "new_password": "NewSecurePass456!"
}
```

#### Success Response

**Status:** `200 OK`

```json
{
  "message": "Password reset successfully!"
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `400 Bad Request` | `{"error": "OTP not verified"}` |
| `404 Not Found` | `{"error": "User not found"}` |

---

### Refresh Token

Refreshes an expired access token using a valid refresh token.

**Endpoint:** `POST /token/refresh/`  
**Authentication:** None

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `refresh` | string | Yes | Valid refresh token |

#### Example Request

```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

#### Success Response

**Status:** `200 OK`

```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

---

## Products

### List Products

Retrieves a paginated list of products owned by the authenticated user.

**Endpoint:** `GET /products/`  
**Authentication:** Required

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page` | integer | No | Page number (default: 1) |

#### Success Response

**Status:** `200 OK`

```json
{
  "count": 25,
  "next": "http://localhost:8000/api/products/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "user": 1,
      "product_name": "Widget A",
      "category": 1,
      "product_Img": "https://example.com/image.jpg",
      "unit_price": "99.99",
      "quantity": 100,
      "description": "A high-quality widget"
    }
  ]
}
```

---

### Create Product

Creates a new product for the authenticated user.

**Endpoint:** `POST /products/`  
**Authentication:** Required

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `product_name` | string | Yes | Product name (unique per user) |
| `category` | integer | Yes | Category ID |
| `unit_price` | decimal | Yes | Price per unit |
| `quantity` | integer | Yes | Stock quantity |
| `product_Img` | string | No | Image URL |
| `description` | string | No | Product description |

#### Example Request

```json
{
  "product_name": "Widget A",
  "category": 1,
  "unit_price": "99.99",
  "quantity": 100,
  "product_Img": "https://example.com/image.jpg",
  "description": "A high-quality widget"
}
```

#### Success Response

**Status:** `201 Created`

```json
{
  "message": "Product created successfully!",
  "product": {
    "id": 1,
    "user": 1,
    "product_name": "Widget A",
    "category": 1,
    "product_Img": "https://example.com/image.jpg",
    "unit_price": "99.99",
    "quantity": 100,
    "description": "A high-quality widget"
  }
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `400 Bad Request` | `{"error": "You already have a product with this name."}` |
| `400 Bad Request` | Validation errors object |

---

### Update Product

Updates an existing product.

**Endpoint:** `PUT /products/?id={product_id}`  
**Authentication:** Required

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | integer | Yes | Product ID to update |

#### Request Body

All fields are optional (partial update supported).

| Field | Type | Description |
|-------|------|-------------|
| `product_name` | string | Product name |
| `category` | integer | Category ID |
| `unit_price` | decimal | Price per unit |
| `quantity` | integer | Stock quantity |
| `product_Img` | string | Image URL |
| `description` | string | Product description |

#### Example Request

```json
{
  "unit_price": "89.99",
  "quantity": 150
}
```

#### Success Response

**Status:** `200 OK`

```json
{
  "message": "Product updated successfully!",
  "product": {
    "id": 1,
    "user": 1,
    "product_name": "Widget A",
    "category": 1,
    "product_Img": "https://example.com/image.jpg",
    "unit_price": "89.99",
    "quantity": 150,
    "description": "A high-quality widget"
  }
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `400 Bad Request` | `{"error": "Product ID is required"}` |
| `400 Bad Request` | `{"error": "Invalid Product ID"}` |
| `404 Not Found` | `{"error": "Product not found or you do not have permission to edit it."}` |

---

### Delete Product

Deletes a product.

**Endpoint:** `DELETE /products/?id={product_id}`  
**Authentication:** Required

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | integer | Yes | Product ID to delete |

#### Success Response

**Status:** `200 OK`

```json
{
  "message": "Product deleted successfully!"
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `400 Bad Request` | `{"error": "Product ID is required"}` |
| `404 Not Found` | `{"error": "Product not found or you do not have permission to delete it."}` |

---

## Parties

Parties represent either Customers or Suppliers.

### List Parties

Retrieves a paginated list of all parties.

**Endpoint:** `GET /parties/`  
**Authentication:** Required

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page` | integer | No | Page number (default: 1) |
| `category_type` | string | No | Filter by type: `Customer` or `Supplier` |

#### Success Response

**Status:** `200 OK`

```json
{
  "count": 50,
  "next": "http://localhost:8000/api/parties/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "Category_type": "Customer",
      "is_active": true,
      "is_updated_at": "2026-02-12T10:30:00Z"
    }
  ]
}
```

---

### Get Party by ID

Retrieves a specific party with related customer/supplier details.

**Endpoint:** `GET /parties/?id={party_id}`  
**Authentication:** Required

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | integer | Yes | Party ID |

#### Success Response (Customer)

**Status:** `200 OK`

```json
{
  "id": 1,
  "Category_type": "Customer",
  "is_active": true,
  "is_updated_at": "2026-02-12T10:30:00Z",
  "customer": {
    "id": 1,
    "party": 1,
    "name": "ABC Company",
    "email": "contact@abc.com",
    "phone_no": "+919876543210",
    "Customer_code": "CUST001",
    "address": "123 Main Street",
    "open_balance": "5000.00",
    "credit_limmit": "50000.00",
    "payment_method": 1,
    "loyalty_points": 100,
    "referred_by": "Jane Doe",
    "notes": "VIP customer"
  }
}
```

#### Success Response (Supplier)

**Status:** `200 OK`

```json
{
  "id": 2,
  "Category_type": "Supplier",
  "is_active": true,
  "is_updated_at": "2026-02-12T10:30:00Z",
  "supplier": {
    "id": 1,
    "party": 2,
    "name": "XYZ Suppliers",
    "code": "SUP001"
  }
}
```

---

### Create Party

Creates a new Customer or Supplier.

**Endpoint:** `POST /parties/`  
**Authentication:** Required

#### Request Body (Customer)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `Category_type` | string | Yes | Must be `Customer` |
| `name` | string | Yes | Customer name |
| `email` | string | No | Email address |
| `phone_no` | string | No | Phone number |
| `Customer_code` | string | No | Unique customer code |
| `address` | string | No | Address |
| `open_balance` | decimal | No | Opening balance (default: 0.00) |
| `credit_limmit` | decimal | No | Credit limit (default: 0.00) |
| `preferred_payment_method` | integer | No | Payment method ID |
| `loyalty_points` | integer | No | Loyalty points (default: 0) |
| `referred_by` | string | No | Referrer name |
| `notes` | string | No | Additional notes |
| `is_active` | boolean | No | Active status (default: true) |

#### Example Request (Customer)

```json
{
  "Category_type": "Customer",
  "name": "ABC Company",
  "email": "contact@abc.com",
  "phone_no": "+919876543210",
  "Customer_code": "CUST001",
  "address": "123 Main Street",
  "open_balance": "5000.00",
  "credit_limmit": "50000.00"
}
```

#### Success Response (Customer)

**Status:** `201 Created`

```json
{
  "message": "Customer created successfully!",
  "party": {
    "id": 1,
    "Category_type": "Customer",
    "is_active": true,
    "is_updated_at": "2026-02-12T10:30:00Z"
  },
  "customer": {
    "id": 1,
    "party": 1,
    "name": "ABC Company",
    "email": "contact@abc.com",
    "phone_no": "+919876543210",
    "Customer_code": "CUST001",
    "address": "123 Main Street",
    "open_balance": "5000.00",
    "credit_limmit": "50000.00",
    "payment_method": null,
    "loyalty_points": 0,
    "referred_by": null,
    "notes": ""
  }
}
```

#### Request Body (Supplier)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `Category_type` | string | Yes | Must be `Supplier` |
| `name` | string | Yes | Supplier name |
| `code` | string | Yes | Unique supplier code |
| `is_active` | boolean | No | Active status (default: true) |

#### Example Request (Supplier)

```json
{
  "Category_type": "Supplier",
  "name": "XYZ Suppliers",
  "code": "SUP001"
}
```

#### Success Response (Supplier)

**Status:** `201 Created`

```json
{
  "message": "Supplier created successfully!",
  "party": {
    "id": 2,
    "Category_type": "Supplier",
    "is_active": true,
    "is_updated_at": "2026-02-12T10:30:00Z"
  },
  "supplier": {
    "id": 1,
    "party": 2,
    "name": "XYZ Suppliers",
    "code": "SUP001"
  }
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `400 Bad Request` | `{"error": "Invalid Category. Must be 'Customer' or 'Supplier'"}` |
| `400 Bad Request` | `{"error": "A customer with this email already exists.", "existing_customer": {...}}` |
| `400 Bad Request` | `{"error": "A customer with this phone number already exists.", "existing_customer": {...}}` |
| `400 Bad Request` | `{"error": "A supplier with this code already exists.", "existing_supplier": {...}}` |

---

### Update Party

Updates an existing party (Customer or Supplier).

**Endpoint:** `PUT /parties/?id={party_id}`  
**Authentication:** Required

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | integer | Yes | Party ID to update |

#### Request Body

All fields are optional (partial update supported). Include fields specific to the party type (Customer or Supplier).

#### Example Request (Customer Update)

```json
{
  "name": "ABC Corporation",
  "credit_limmit": "75000.00",
  "loyalty_points": 150
}
```

#### Success Response (Customer)

**Status:** `200 OK`

```json
{
  "message": "Customer updated successfully!",
  "party": {
    "id": 1,
    "Category_type": "Customer",
    "is_active": true,
    "is_updated_at": "2026-02-12T12:00:00Z"
  },
  "customer": {
    "id": 1,
    "party": 1,
    "name": "ABC Corporation",
    "email": "contact@abc.com",
    "phone_no": "+919876543210",
    "Customer_code": "CUST001",
    "address": "123 Main Street",
    "open_balance": "5000.00",
    "credit_limmit": "75000.00",
    "payment_method": null,
    "loyalty_points": 150,
    "referred_by": null,
    "notes": ""
  }
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `400 Bad Request` | `{"error": "Party ID is required"}` |
| `400 Bad Request` | `{"error": "No related customer or supplier found"}` |
| `404 Not Found` | `{"error": "Party not found"}` |

---

### Delete Party

Deletes a party and its related customer/supplier data.

**Endpoint:** `DELETE /parties/?id={party_id}`  
**Authentication:** Required

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | integer | Yes | Party ID to delete |

#### Success Response

**Status:** `200 OK`

```json
{
  "message": "Party deleted successfully!"
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `400 Bad Request` | `{"error": "Party ID is required"}` |
| `404 Not Found` | `{"error": "Party not found"}` |

---

## Expenses

### List Expenses

Retrieves a paginated list of expenses for the authenticated user.

**Endpoint:** `GET /expenses/`  
**Authentication:** Required

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page` | integer | No | Page number (default: 1) |

#### Success Response

**Status:** `200 OK`

```json
{
  "count": 15,
  "next": "http://localhost:8000/api/expenses/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "user": 1,
      "amount": "5000.00",
      "description": "Office rent for February",
      "date": "2026-02-01",
      "category": "Rent",
      "is_necessary": true
    }
  ]
}
```

---

### Create Expense

Creates a new expense record.

**Endpoint:** `POST /expenses/`  
**Authentication:** Required

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `amount` | decimal | Yes | Expense amount |
| `date` | date | Yes | Expense date (YYYY-MM-DD) |
| `category` | string | Yes | One of: `Rent`, `Utilities`, `Salary`, `Inventory`, `Transport`, `Food`, `Office Supplies`, `Phone`, `Marketing`, `Other` |
| `description` | string | No | Description |
| `is_necessary` | boolean | No | Whether expense is necessary (default: true) |

#### Example Request

```json
{
  "amount": "5000.00",
  "date": "2026-02-01",
  "category": "Rent",
  "description": "Office rent for February",
  "is_necessary": true
}
```

#### Success Response

**Status:** `201 Created`

```json
{
  "message": "Expense created successfully!",
  "expense": {
    "id": 1,
    "user": 1,
    "amount": "5000.00",
    "description": "Office rent for February",
    "date": "2026-02-01",
    "category": "Rent",
    "is_necessary": true
  }
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `400 Bad Request` | Validation errors object |

---

### Update Expense

Updates an existing expense.

**Endpoint:** `PUT /expenses/?id={expense_id}`  
**Authentication:** Required

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | integer | Yes | Expense ID to update |

#### Request Body

All fields are optional (partial update supported).

#### Example Request

```json
{
  "amount": "5500.00",
  "description": "Office rent for February (revised)"
}
```

#### Success Response

**Status:** `200 OK`

```json
{
  "message": "Expense updated successfully!",
  "expense": {
    "id": 1,
    "user": 1,
    "amount": "5500.00",
    "description": "Office rent for February (revised)",
    "date": "2026-02-01",
    "category": "Rent",
    "is_necessary": true
  }
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `400 Bad Request` | `{"error": "Expense ID is required"}` |
| `400 Bad Request` | `{"error": "Invalid Expense ID"}` |
| `404 Not Found` | `{"error": "Expense not found or you do not have permission to edit it."}` |

---

### Delete Expense

Deletes an expense record.

**Endpoint:** `DELETE /expenses/?id={expense_id}`  
**Authentication:** Required

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | integer | Yes | Expense ID to delete |

#### Success Response

**Status:** `200 OK`

```json
{
  "message": "Expense deleted successfully!"
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `400 Bad Request` | `{"error": "Expense ID is required"}` |
| `404 Not Found` | `{"error": "Expense not found or you do not have permission to delete it."}` |

---

## Billing

### List Billings

Retrieves a paginated list of billing records for the authenticated user.

**Endpoint:** `GET /billing/`  
**Authentication:** Required

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `page` | integer | No | Page number (default: 1) |

#### Success Response

**Status:** `200 OK`

```json
{
  "count": 30,
  "next": "http://localhost:8000/api/billing/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "user": 1,
      "invoice_number": "INV-2026-001",
      "invoice_date": "2026-02-12",
      "due_date": "2026-03-12",
      "payment_method": 1,
      "invoice_status": "Unpaid",
      "party": 1,
      "phone": "+919876543210",
      "VAt_number": "VATIN12345",
      "address": "123 Main Street",
      "notes": "Payment due in 30 days",
      "paid_amount": "0.00",
      "due_amount": "15000.00",
      "total_amount": "15000.00",
      "discount": "500.00",
      "tax": "2700.00",
      "sub_total": "12800.00"
    }
  ]
}
```

---

### Create Billing

Creates a new billing record with line items.

**Endpoint:** `POST /billing/`  
**Authentication:** Required

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `invoice_number` | string | Yes | Unique invoice number |
| `invoice_date` | date | No | Invoice date (YYYY-MM-DD) |
| `due_date` | date | No | Due date (YYYY-MM-DD) |
| `payment_method` | integer | No | Payment method ID |
| `invoice_status` | string | No | One of: `Paid`, `Unpaid`, `Pending`, `Draft` (default: `Draft`) |
| `party` | integer | No | Party (Customer) ID |
| `phone` | string | No | Customer phone |
| `VAt_number` | string | No | VAT number |
| `address` | string | No | Billing address |
| `notes` | string | No | Additional notes |
| `paid_amount` | decimal | No | Amount paid (default: 0.00) |
| `due_amount` | decimal | No | Amount due (default: 0.00) |
| `total_amount` | decimal | No | Total amount (default: 0.00) |
| `discount` | decimal | No | Discount amount (default: 0.00) |
| `tax` | decimal | No | Tax amount (default: 0.00) |
| `sub_total` | decimal | No | Subtotal (default: 0.00) |
| `items` | array | Yes | Array of billing items (min 1 required) |

#### Billing Item Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `item` | integer | Yes | Product ID |
| `quantity` | integer | Yes | Quantity |
| `rate` | decimal | Yes | Rate per unit |

#### Example Request

```json
{
  "invoice_number": "INV-2026-001",
  "invoice_date": "2026-02-12",
  "due_date": "2026-03-12",
  "party": 1,
  "phone": "+919876543210",
  "address": "123 Main Street",
  "invoice_status": "Unpaid",
  "sub_total": "12800.00",
  "discount": "500.00",
  "tax": "2700.00",
  "total_amount": "15000.00",
  "due_amount": "15000.00",
  "notes": "Payment due in 30 days",
  "items": [
    {
      "item": 1,
      "quantity": 10,
      "rate": "99.99"
    },
    {
      "item": 2,
      "quantity": 5,
      "rate": "199.99"
    }
  ]
}
```

#### Success Response

**Status:** `201 Created`

```json
{
  "message": "Billing created successfully!",
  "billing": {
    "id": 1,
    "user": 1,
    "invoice_number": "INV-2026-001",
    "invoice_date": "2026-02-12",
    "due_date": "2026-03-12",
    "payment_method": null,
    "invoice_status": "Unpaid",
    "party": 1,
    "phone": "+919876543210",
    "VAt_number": null,
    "address": "123 Main Street",
    "notes": "Payment due in 30 days",
    "paid_amount": "0.00",
    "due_amount": "15000.00",
    "total_amount": "15000.00",
    "discount": "500.00",
    "tax": "2700.00",
    "sub_total": "12800.00"
  }
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `400 Bad Request` | `{"error": "At least one billing item is required."}` |
| `400 Bad Request` | Validation errors object |

---

### Update Billing

Updates an existing billing record.

**Endpoint:** `PUT /billing/?id={billing_id}`  
**Authentication:** Required

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | integer | Yes | Billing ID to update |

#### Request Body

All fields are optional (partial update supported).

#### Example Request

```json
{
  "invoice_status": "Paid",
  "paid_amount": "15000.00",
  "due_amount": "0.00"
}
```

#### Success Response

**Status:** `200 OK`

```json
{
  "message": "Billing updated successfully!",
  "billing": {
    "id": 1,
    "user": 1,
    "invoice_number": "INV-2026-001",
    "invoice_date": "2026-02-12",
    "due_date": "2026-03-12",
    "payment_method": null,
    "invoice_status": "Paid",
    "party": 1,
    "phone": "+919876543210",
    "VAt_number": null,
    "address": "123 Main Street",
    "notes": "Payment due in 30 days",
    "paid_amount": "15000.00",
    "due_amount": "0.00",
    "total_amount": "15000.00",
    "discount": "500.00",
    "tax": "2700.00",
    "sub_total": "12800.00"
  }
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `400 Bad Request` | `{"error": "Billing ID is required"}` |
| `400 Bad Request` | `{"error": "Invalid Billing ID"}` |
| `404 Not Found` | `{"error": "Billing not found or you do not have permission to edit it."}` |

---

### Delete Billing

Deletes a billing record.

**Endpoint:** `DELETE /billing/?id={billing_id}`  
**Authentication:** Required

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | integer | Yes | Billing ID to delete |

#### Success Response

**Status:** `200 OK`

```json
{
  "message": "Billing deleted successfully!"
}
```

#### Error Responses

| Status | Response |
|--------|----------|
| `400 Bad Request` | `{"error": "Billing ID is required"}` |
| `404 Not Found` | `{"error": "Billing not found or you do not have permission to delete it."}` |

---

## Error Codes

| HTTP Status | Description |
|-------------|-------------|
| `200 OK` | Request successful |
| `201 Created` | Resource created successfully |
| `204 No Content` | Resource deleted successfully |
| `400 Bad Request` | Invalid request data or validation error |
| `401 Unauthorized` | Invalid or missing authentication |
| `403 Forbidden` | Access denied |
| `404 Not Found` | Resource not found |
| `500 Internal Server Error` | Server error |

---

## Data Models

### User Profile

| Field | Type | Description |
|-------|------|-------------|
| `phone_no` | string | Phone number (max 15 chars) |
| `business_name` | string | Business name (max 255 chars) |
| `is_verify` | boolean | Email verification status |

### Product

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Primary key |
| `user` | integer | Owner user ID |
| `product_name` | string | Product name (max 100 chars) |
| `category` | integer | Category ID |
| `sku` | string | Unique SKU (max 50 chars) |
| `product_Img` | string | Image URL |
| `unit_price` | decimal | Price (max 10 digits, 2 decimals) |
| `quantity` | integer | Stock quantity |
| `description` | string | Product description |

### Party

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Primary key |
| `Category_type` | string | `Customer` or `Supplier` |
| `is_active` | boolean | Active status |
| `is_updated_at` | datetime | Last updated timestamp |

### Customer

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Primary key |
| `party` | integer | Party ID |
| `name` | string | Customer name |
| `email` | string | Email address |
| `phone_no` | string | Phone number |
| `Customer_code` | string | Unique customer code |
| `address` | string | Address |
| `open_balance` | decimal | Opening balance |
| `credit_limmit` | decimal | Credit limit |
| `payment_method` | integer | Payment method ID |
| `loyalty_points` | integer | Loyalty points |
| `referred_by` | string | Referrer name |
| `notes` | string | Notes |

### Supplier

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Primary key |
| `party` | integer | Party ID |
| `name` | string | Supplier name |
| `code` | string | Unique supplier code |

### Expense

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Primary key |
| `user` | integer | Owner user ID |
| `category` | string | Expense category |
| `amount` | decimal | Expense amount |
| `description` | string | Description |
| `date` | date | Expense date |
| `is_necessary` | boolean | Necessity flag |

### Billing

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Primary key |
| `user` | integer | Owner user ID |
| `invoice_number` | string | Unique invoice number |
| `invoice_date` | date | Invoice date |
| `due_date` | date | Due date |
| `payment_method` | integer | Payment method ID |
| `invoice_status` | string | `Paid`, `Unpaid`, `Pending`, `Draft` |
| `party` | integer | Customer party ID |
| `phone` | string | Customer phone |
| `VAt_number` | string | VAT number |
| `address` | string | Billing address |
| `notes` | string | Notes |
| `paid_amount` | decimal | Amount paid |
| `due_amount` | decimal | Amount due |
| `total_amount` | decimal | Total amount |
| `discount` | decimal | Discount |
| `tax` | decimal | Tax amount |
| `sub_total` | decimal | Subtotal |

### Billing Item

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Primary key |
| `billing` | integer | Billing ID |
| `item` | integer | Product ID |
| `quantity` | integer | Quantity |
| `rate` | decimal | Rate per unit |

---

## Rate Limiting

Currently, no rate limiting is implemented.

## Versioning

API version 1.0.0 - No versioning prefix in URLs currently.

---

*Last Updated: February 12, 2026*
