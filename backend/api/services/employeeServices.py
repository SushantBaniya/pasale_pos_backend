from decimal import Decimal
import json
from api.models import Employee, Business, Department
from api.serializers import EmployeeSerializer
from rest_framework.response import Response
from rest_framework import status


def get_all_employees(business_id, employee_id=None):
    if not business_id:
        return Response({"error": "Business ID is required"}, status=status.HTTP_400_BAD_REQUEST)

    # validate if business_id is valid
    try:
        business = Business.objects.filter(id=business_id).first()
    except business.DoesNotExist:
        return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)

    # for a single employee
    if employee_id:
        employee = Employee.objects.filter(
            id=employee_id, business_id=business_id
        ).select_related('department', 'business_id', 'status', 'manager').first()
        if not employee:
            return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = EmployeeSerializer(employee)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # for all employees in a business
    employees = Employee.objects.filter(business_id=business_id).select_related(
        'department', 'business_id', 'status', 'manager'
    ).prefetch_related('skills__skill')
    serializer = EmployeeSerializer(employees, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


def create_employee(business_id, data):
    try:
        # Normalize DRF request data safely (dict / QueryDict / JSON string).
        if hasattr(data, 'dict'):
            data = data.dict()
        elif isinstance(data, dict):
            data = data.copy()
        elif isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return Response({"error": "Invalid JSON payload. Expected an object."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            try:
                data = dict(data)
            except (TypeError, ValueError):
                return Response({"error": "Invalid payload format. Expected a JSON object."}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(data, dict):
            return Response({"error": "Invalid payload format. Expected a JSON object."}, status=status.HTTP_400_BAD_REQUEST)

        # Add business_id to data
        data['business_id'] = business_id

        # Required fields
        required_fields = ['business_id', 'name',
                           'phone_no', 'email', 'position']
        for field in required_fields:
            if field not in data:
                return Response({"error": f"{field} is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate if business_id is valid
        try:
            business = Business.objects.filter(id=business_id).first()
            if not business:
                return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        except Business.DoesNotExist:
            return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)

        # Ensure department exists if provided
        dept_name = data.get('department')
        if dept_name and isinstance(dept_name, str):
            Department.objects.get_or_create(name=dept_name, business_id_id=business_id)

        serializer = EmployeeSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
