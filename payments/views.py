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
import stripe
from django.http import HttpResponse

stripe.api_key = settings.STRIPE_SECRET_KEY
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
            if user.subscription_end and user.subscription_end > timezone.localdate():
                user.subscription_end += timedelta(days=30)
            else:
                user.subscription_end = timezone.localdate() + timedelta(days=30)

            user.save(update_fields=["user_type", "subscription_end"])
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)
        

    return JsonResponse({
        "md5": md5,
        "status": payment_status
    })


@csrf_exempt
def create_checkout_session(request):
    if request.method != "POST":
        return JsonResponse({'error': 'POST required'}, status=400)

    try:
        data = json.loads(request.body.decode('utf-8'))
        user_id = data.get("user_id")
        amount = float(data.get("amount", 10.00))
        currency = data.get("currency", "usd")

        # Stripe checkout WITHOUT redirect URLs
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            mode='payment',
            line_items=[{
                'price_data': {
                    'currency': currency,
                    'product_data': {'name': 'Premium Subscription'},
                    'unit_amount': int(amount * 100),
                },
                'quantity': 1,
            }],
            success_url="myapp://payments/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="myapp://payments/cancel",
        )

        # Save transaction
        PaymentTransaction.objects.create(
            user_id=user_id,
            bill_number=f"STRIPE-{session.id[-8:]}",
            amount=amount,
            currency=currency.upper(),
            md5_hash=session.id,
            qr_string="",
            deeplink=session.url,
            status="UNPAID",
        )

        return JsonResponse({
            "success": True,
            "checkout_url": session.url,
            "session_id": session.id,
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@csrf_exempt
def check_payment_status_stripe(request):
    session_id = request.GET.get("session_id")

    if not session_id:
        return JsonResponse({"error": "session_id required"}, status=400)

    # Stripe only: find Txn by Stripe session ID
    txn = PaymentTransaction.objects.filter(md5_hash=session_id).first()

    if not txn:
        return JsonResponse({"status": "NOT_FOUND"})

    # 🔥 If Stripe webhook already marked as PAID
    if txn.status == "PAID":
        user = txn.user
        if user:
            # Update subscription only once
            if not user.subscription_end or user.subscription_end < timezone.localdate():
                user.subscription_end = timezone.localdate() + timedelta(days=30)
            else:
                user.subscription_end += timedelta(days=30)

            user.user_type = "subscription"
            user.save(update_fields=["subscription_end", "user_type"])
            print(f"🔥 Stripe Subscription Activated for {user.username}")

        return JsonResponse({
            "status": "PAID",
            "amount": str(txn.amount),
            "currency": txn.currency,
            "user": txn.user.username if txn.user else None,
        })

    # ⏳ Payment still UNPAID
    return JsonResponse({
        "status": txn.status,
        "amount": str(txn.amount),
        "currency": txn.currency,
        "user": txn.user.username if txn.user else None,
    })


# # ✅ Create Checkout Session for Mobile
# @csrf_exempt
# def create_checkout_session(request):
#     if request.method != "POST":
#         return JsonResponse({'error': 'POST required'}, status=400)

#     try:
#         data = json.loads(request.body.decode('utf-8'))
#         user_id = data.get("user_id")
#         amount = float(data.get("amount", 10.00))
#         currency = data.get("currency", "usd")

#         # Stripe checkout session
#         session = stripe.checkout.Session.create(
#             payment_method_types=['card'],
#             mode='payment',
#             line_items=[{
#                 'price_data': {
#                     'currency': currency,
#                     'product_data': {'name': 'Premium Subscription'},
#                     'unit_amount': int(amount * 100),
#                 },
#                 'quantity': 1,
#             }],
#             success_url="myapp://payments/success?session_id={CHECKOUT_SESSION_ID}",
#             cancel_url="myapp://payments/cancel",
#         )

#         # Save transaction
#         PaymentTransaction.objects.create(
#             user_id=user_id,
#             bill_number=f"STRIPE-{session.id[-8:]}",
#             amount=amount,
#             currency=currency.upper(),
#             md5_hash=session.id,
#             qr_string="",
#             deeplink=session.url,
#             status="UNPAID",
#         )

#         return JsonResponse({
#             "success": True,
#             "checkout_url": session.url,
#             "session_id": session.id,
#         })
#     except Exception as e:
#         return JsonResponse({"success": False, "error": str(e)}, status=500)

# @csrf_exempt
# def check_payment_status(request):
#     session_id = request.GET.get("session_id") or request.GET.get("md5")
#     if not session_id:
#         return JsonResponse({"error": "session_id required"}, status=400)

#     txn = PaymentTransaction.objects.filter(md5_hash=session_id).first()
#     if not txn:
#         return JsonResponse({"status": "NOT_FOUND"})

#     return JsonResponse({
#         "status": txn.status,
#         "amount": str(txn.amount),
#         "currency": txn.currency,
#         "user": txn.user.username if txn.user else None,
#     })

# # ✅ Webhook for Payment Confirmation
# @csrf_exempt
# def stripe_webhook(request):
#     payload = request.body
#     sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
#     try:
#         event = stripe.Webhook.construct_event(
#             payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
#         )
#     except Exception as e:
#         return JsonResponse({'error': str(e)}, status=400)

#     if event['type'] == 'checkout.session.completed':
#         session = event['data']['object']
#         session_id = session.get('id')
#         print(f"✅ Webhook received: {session_id}")

#         txn = PaymentTransaction.objects.filter(md5_hash=session_id).first()
#         if txn:
#             txn.status = "PAID"
#             txn.save()

#             user = txn.user
#             if user:
#                 user.user_type = "subscription"
#                 if user.subscription_end and user.subscription_end > timezone.localdate():
#                     user.subscription_end += timedelta(days=30)
#                 else:
#                     user.subscription_end = timezone.localdate() + timedelta(days=30)
#                 user.save(update_fields=["user_type", "subscription_end"])
#                 print(f"✅ Subscription updated for {user.username}")

#     return JsonResponse({'status': 'success'})