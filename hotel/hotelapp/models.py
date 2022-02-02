from django.db import models

class Profile(models.Model):
    """
    Класс Профиль пользователя. Атрибуты extr_id - уникальный id пользователя (chat_id телеграмм).
    Name - имя пользователя (телеграмм), city - местонахождение или город поиска.
    city_id - ID города в rapidapi
    """
    extr_id = models.PositiveIntegerField(
        verbose_name='User ID'
    )
    name = models.TextField(
        verbose_name='User name'
    )
    city = models.TextField(
        verbose_name='Location',
        default='None',
    )
    city_id = models.IntegerField(
        verbose_name='City ID',
        default=0
    )
    dist_min = models.IntegerField(
        verbose_name='Min dist center',
        default=0
    )
    dist_max = models.IntegerField(
        verbose_name='Max dist center',
        default=999
    )
    price_min = models.FloatField(
        verbose_name='min price',
        default=0
    )
    price_max = models.FloatField(
        verbose_name='max price',
        default=9999999
    )
    page_size = models.IntegerField(
        verbose_name='number of hotels',
        default=1
    )
    def __str__(self):
        return  f'{self.extr_id} {self.name}'

    class Meta:
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'

class Message(models.Model):
    profile = models.ForeignKey(
        to = 'hotelapp.Profile',
        verbose_name='Profile',
        on_delete=models.PROTECT,
    )
    text = models.TextField(
        verbose_name='Text',
    )
    created_at = models.DateTimeField(
        verbose_name='Time of receipt',
        auto_now_add=True
    )

    def __str__(self):
        return f'Message {self.pk} от {self.profile}'

    class Meta:
        verbose_name = 'Message',
        verbose_name_plural = 'Messages'