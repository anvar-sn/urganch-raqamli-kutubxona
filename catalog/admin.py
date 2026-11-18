import csv
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http import HttpResponse
from .models import (
    User,
    Book,
    Category,
    Favorite,
    ReadingEvent,
    ReadingProgress,
    Notification,
    Quiz,
    Question,
    AnswerOption,
    QuizAttempt,
    ContactMessage,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Litsey ma’lumotlari', {'fields': ('role', 'group_name', 'points')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Litsey ma’lumotlari', {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'role', 'group_name', 'email'),
        }),
    )
    list_display = (
        'username',
        'first_name',
        'last_name',
        'role',
        'group_name',
        'points',
        'is_active',
        'is_staff',
    )
    list_filter = ('role', 'is_active', 'is_staff', 'group_name')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'group_name')


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'author',
        'subject',
        'is_teacher_book',
        'approved',
        'featured',
        'view_count',
        'download_count',
        'created_at',
    )
    list_filter = ('approved', 'featured', 'is_teacher_book', 'subject', 'language', 'category')
    search_fields = ('title', 'author', 'subject', 'description', 'isbn')
    list_editable = ('approved', 'featured', 'is_teacher_book')
    readonly_fields = ('view_count', 'download_count', 'created_at')
    actions = ('export_as_csv',)

    @admin.action(description='Tanlangan kitoblarni CSV formatida eksport qilish')
    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename=kutubxona-kitoblari.csv'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow([
            'Kitob nomi',
            'Muallif',
            'Fan',
            'Kategoriya',
            'Til',
            'Nashr yili',
            'O‘qituvchi kitobi',
            'Tasdiqlangan',
            'Ko‘rishlar',
            'Yuklab olishlar',
        ])
        for book in queryset.select_related('category'):
            writer.writerow([
                book.title,
                book.author,
                book.subject,
                book.category.name if book.category else '',
                book.language,
                book.published_year or '',
                'Ha' if book.is_teacher_book else 'Yo‘q',
                'Ha' if book.approved else 'Yo‘q',
                book.view_count,
                book.download_count,
            ])
        return response


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ('name',)


class AnswerInline(admin.TabularInline):
    model = AnswerOption
    extra = 4


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'is_published', 'created_by', 'created_at')
    list_filter = ('is_published', 'subject')
    search_fields = ('title', 'description', 'subject')
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'quiz', 'order')
    inlines = [AnswerInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'quiz', 'score', 'total', 'certificate_code', 'created_at')
    list_filter = ('quiz', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'certificate_code')


@admin.register(ContactMessage)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('name', 'email', 'message')


admin.site.register([Favorite, ReadingEvent, ReadingProgress, Notification, AnswerOption])
admin.site.site_header = 'Urganch akademik litseyi — Kutubxona boshqaruvi'
admin.site.site_title = 'Raqamli kutubxona'
admin.site.index_title = 'Tizim boshqaruvi'
