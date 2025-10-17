from django.db import models
from django.conf import settings

class PaymentTransaction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bill_number = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10)
    md5_hash = models.CharField(max_length=64)
    qr_string = models.TextField()
    deeplink = models.URLField()
    status = models.CharField(max_length=20, default="UNPAID")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.bill_number} - {self.status}"
