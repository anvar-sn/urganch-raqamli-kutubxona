from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, re_path
from django.views.static import serve
from catalog import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('healthz/', views.health_check, name='health_check'),
    path('', views.home, name='home'),
    path('sign-in', views.login_view, name='sign_in_no_slash'),
    path('sign-in/', views.login_view, name='sign_in'),
    path('dashboard', views.dashboard, name='dashboard_uzedu_no_slash'),
    path('dashboard/', views.dashboard, name='dashboard_uzedu'),
    path('school-library/', views.home, name='school_library'),
    path('fiction-books/', views.home, name='fiction_books'),
    path('interaktiv/', views.legacy_index, name='legacy_index'),
    path('service-worker.js', views.service_worker, name='service_worker'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path(
        'parolni-tiklash/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset_form.html',
            email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
        ),
        name='password_reset',
    ),
    path(
        'parol-tiklandi/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html'
        ),
        name='password_reset_done',
    ),
    path(
        'parolni-tiklash/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html'
        ),
        name='password_reset_confirm',
    ),
    path(
        'parol-yangilandi/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html'
        ),
        name='password_reset_complete',
    ),
    path('kitob/<int:pk>/', views.book_detail, name='book_detail'),
    path('kitob/<int:pk>/pdf/', views.book_pdf, name='book_pdf'),
    path('kitob/<int:pk>/fayl/', views.book_pdf_file, name='book_pdf_file'),
    path('kitob/<int:pk>/yuklab-olish/', views.download_book_file, name='download_book_file'),
    path('kitob/<int:pk>/qrcode/', views.book_qrcode, name='book_qrcode'),
    path('kitob/<int:pk>/progress/', views.save_progress, name='save_progress'),
    path('kitob/<int:pk>/sevimli/', views.toggle_favorite, name='toggle_favorite'),
    path('sevimlilar/', views.favorites, name='favorites'),
    path('kabinet/', views.dashboard, name='dashboard'),
    path('profil/', views.dashboard, name='profile'),
    path('profile/', views.dashboard, name='profile_alias'),
    path('admin-panel/foydalanuvchi/qoshish/', views.admin_add_user, name='admin_add_user'),
    path('admin-panel/foydalanuvchi/<int:pk>/tahrirlash/', views.admin_edit_user, name='admin_edit_user'),
    path('admin-panel/foydalanuvchi/<int:pk>/faollik/', views.admin_toggle_user_active, name='admin_toggle_user_active'),
    path('admin-panel/foydalanuvchi/<int:pk>/ochirish/', views.admin_delete_user, name='admin_delete_user'),
    path('admin-panel/foydalanuvchi/<int:pk>/rol-ozgartirish/', views.admin_change_user_role, name='admin_change_user_role'),
    path('admin-panel/kitob/<int:pk>/ochirish/', views.admin_delete_book, name='admin_delete_book'),
    path('admin-panel/kitob/<int:pk>/tasdiqlash/', views.admin_approve_book, name='admin_approve_book'),
    path('admin-panel/kitob/<int:pk>/ustoz-holati/', views.admin_toggle_teacher_book, name='admin_toggle_teacher_book'),
    path('manba/<str:dl_id>/muqova/', views.ziyouz_cover, name='ziyouz_cover'),
    path('manba/<str:dl_id>/ochish/', views.ziyouz_open_book, name='ziyouz_open_book'),
    path('kitob-yuklash/', views.upload_book, name='upload_book'),
    path('oqituvchilar-kitoblari/', views.teachers_books, name='teachers_books'),
    path('reyting/', views.leaderboard, name='leaderboard'),
    path('testlar/', views.quiz_list, name='quiz_list'),
    path('test-yaratish/', views.create_quiz, name='create_quiz'),
    path('test-yaratish/import/', views.parse_quiz_import_api, name='parse_quiz_import_api'),
    path('testlar/<int:pk>/ochirish/', views.delete_quiz, name='delete_quiz'),
    path('testlar/<int:pk>/', views.take_quiz, name='take_quiz'),
    path('test-natija/<int:pk>/', views.quiz_result, name='quiz_result'),
    path('sertifikat/<int:pk>/', views.certificate_view, name='certificate_view'),
    path('sertifikat/<int:pk>/qrcode/', views.certificate_qrcode, name='certificate_qrcode'),
    path('bildirishnoma/<int:pk>/oqildi/', views.mark_notification_read, name='mark_notification_read'),
    path('api/kutubxonachi/', views.ai_librarian, name='ai_librarian'),
    path('api/ziyouz/', views.ziyouz_search_api, name='ziyouz_search_api'),
    path('api/ziyouz-search/', views.ziyouz_search_api, name='ziyouz_search_api_alias'),
    path('api/pdf/', views.pdf_proxy, name='pdf_proxy'),
    path('api/pdf-topish/', views.pdf_resolve, name='pdf_resolve'),
    path('murojaat/', views.contact, name='contact'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    media_prefix = settings.MEDIA_URL.lstrip('/')
    urlpatterns += [
        re_path(rf'^{media_prefix}(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]
