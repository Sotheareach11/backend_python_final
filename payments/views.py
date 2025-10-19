import os
import qrcode
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from bakong_khqr import KHQR
from .models import PaymentTransaction
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
import json

User = get_user_model()


@csrf_exempt
def generate_khqr(request):
    khqr = KHQR("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImlkIjoiY2JhZTIwMjVjZWFhNDhkYyJ9LCJpYXQiOjE3NjA2NzIwNTgsImV4cCI6MTc2ODQ0ODA1OH0.oBv-JPoDKOQRz3kCvLHqKQZ3zmC6fiCENFXwGBkecb4")

    qr_string = khqr.create_qr(
        bank_account='meas_sotheareach@aclb',
        merchant_name='SOTHEAREACH MEAS',
        merchant_city='PhnomPenh',
        amount=0.01,
        currency='USD',
        store_label='MShop',
        phone_number='85517335231',
        bill_number='TRX01234567',
        terminal_label='Cashier-01',
        static=False
    )

    md5 = khqr.generate_md5(qr_string)
    payment_status = khqr.check_payment(md5)

    # ✅ Create QR image and save it to /media/khqr/
    qr_img = qrcode.make(qr_string)
    folder_path = os.path.join(settings.MEDIA_ROOT, 'khqr')
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"{md5}.png")
    qr_img.save(file_path)

    # ✅ Construct public URL for Flutter
    qr_image_url = request.build_absolute_uri(f"/media/khqr/{md5}.png")


    return JsonResponse({
        "qr": qr_string,
        "qr_image_url": qr_image_url,
        "md5": md5,
        "status": payment_status,
    })


@csrf_exempt
def check_payment_status(request):
    # Accept both GET and POST
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            md5 = data.get("md5")
            user_id = data.get("user_id")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
    else:
        md5 = request.GET.get("md5")
        user_id = request.GET.get("user_id")

    if not md5 or not user_id:
        return JsonResponse({"error": "md5 and user_id required"}, status=400)

    # ✅ KHQR payment check
    khqr = KHQR("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImlkIjoiY2JhZTIwMjVjZWFhNDhkYyJ9LCJpYXQiOjE3NjA2NzIwNTgsImV4cCI6MTc2ODQ0ODA1OH0.oBv-JPoDKOQRz3kCvLHqKQZ3zmC6fiCENFXwGBkecb4")

    try:
        payment_status = khqr.check_payment(md5)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    # ✅ Update local transaction
    try:
        txn = PaymentTransaction.objects.get(md5_hash=md5)
        txn.status = payment_status
        txn.save()
    except PaymentTransaction.DoesNotExist:
        pass

    # ✅ If paid, update user subscription
    if payment_status == "PAID":
        try:
            user = User.objects.get(id=user_id)
            user.user_type = "subscription"
            if user.subscription_end and user.subscription_end > timezone.now():
                user.subscription_end += timedelta(days=30)
            else:
                # Case 2: if expired or never set → start new 30 days from today
                user.subscription_end = timezone.now() + timedelta(days=30)

            user.save(update_fields=["user_type", "subscription_end"])
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)
        

    return JsonResponse({
        "md5": md5,
        "status": payment_status
    })