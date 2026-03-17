from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Category, Favorite, Item, ItemImage, Message, Report, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    fieldsets = UserAdmin.fieldsets + (
        ('University Info', {'fields': ('university_email', 'student_id')}),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}


class ItemImageInline(admin.TabularInline):
    model = ItemImage
    extra = 1


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'category', 'price', 'condition', 'status', 'created_at')
    list_filter = ('category', 'condition', 'status')
    search_fields = ('title', 'description')
    inlines = [ItemImageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('item', 'sender', 'recipient', 'created_at', 'is_read')
    list_filter = ('is_read',)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'item', 'created_at')
    search_fields = ('user__username', 'item__title')


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('item', 'reporter', 'reason', 'status', 'reviewed_by', 'created_at')
    list_filter = ('reason', 'status')
    search_fields = ('item__title', 'reporter__username')
