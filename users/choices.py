from django.db import models

class AUTH_PROVIDERS(models.TextChoices):
    EMAIL = 'email', 'Email'
    GOOGLE = 'google', 'Google'

class LANGUAGES(models.TextChoices):
    EN = 'en', 'English'
    AR = 'ar', 'Arabic'

class COLOR_MODES(models.TextChoices):
    LIGHT = 'light', 'Light'
    DARK = 'dark', 'Dark'

class CURRENCIES(models.TextChoices):
    # 🔵 أساسية
    USD = 'USD', 'USD'
    EUR = 'EUR', 'EUR'
    GBP = 'GBP', 'GBP'
    EGP = 'EGP', 'EGP'

    # 🌍 أوروبا
    CHF = 'CHF', 'CHF'  # سويسرا
    SEK = 'SEK', 'SEK'  # السويد
    NOK = 'NOK', 'NOK'  # النرويج
    DKK = 'DKK', 'DKK'  # الدنمارك
    PLN = 'PLN', 'PLN'  # بولندا
    CZK = 'CZK', 'CZK'  # التشيك
    HUF = 'HUF', 'HUF'  # المجر
    RON = 'RON', 'RON'  # رومانيا

    # 🌎 أمريكا
    CAD = 'CAD', 'CAD'  # كندا
    BRL = 'BRL', 'BRL'  # البرازيل
    MXN = 'MXN', 'MXN'  # المكسيك
    ARS = 'ARS', 'ARS'  # الأرجنتين
    CLP = 'CLP', 'CLP'  # تشيلي

    # 🌏 آسيا (مهم جدًا للجيمنج)
    JPY = 'JPY', 'JPY'  # اليابان
    KRW = 'KRW', 'KRW'  # كوريا
    CNY = 'CNY', 'CNY'  # الصين
    HKD = 'HKD', 'HKD'  # هونج كونج
    TWD = 'TWD', 'TWD'  # تايوان
    SGD = 'SGD', 'SGD'  # سنغافورة
    MYR = 'MYR', 'MYR'  # ماليزيا
    THB = 'THB', 'THB'  # تايلاند
    INR = 'INR', 'INR'  # الهند
    IDR = 'IDR', 'IDR'  # إندونيسيا
    PHP = 'PHP', 'PHP'  # الفلبين
    VND = 'VND', 'VND'  # فيتنام

    # 🌍 الشرق الأوسط (مهم جدًا للشراء)
    SAR = 'SAR', 'SAR'  # السعودية
    AED = 'AED', 'AED'  # الإمارات
    QAR = 'QAR', 'QAR'  # قطر
    KWD = 'KWD', 'KWD'  # الكويت
    BHD = 'BHD', 'BHD'  # البحرين
    OMR = 'OMR', 'OMR'  # عمان
    TRY = 'TRY', 'TRY'  # تركيا

    # 🌍 أفريقيا
    ZAR = 'ZAR', 'ZAR'  # جنوب أفريقيا
    NGN = 'NGN', 'NGN'  # نيجيريا
    

class Role(models.TextChoices):
    USER = 'user', 'User'
    ADMIN = 'admin', 'Admin'
    SELLER = 'seller', 'Seller'
    DEVELOPER = 'developer', 'Developer'