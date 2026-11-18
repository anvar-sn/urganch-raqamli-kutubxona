import io
import ipaddress
import json
import re as _re
import secrets
import socket
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path

from django.conf import settings as _settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .covers import render_pdf_cover_bytes
from .forms import BookForm, ContactForm, RegisterForm
from .quiz_parser import QUIZ_TEMPLATE_TEXT, extract_text_from_uploaded_file, parse_quiz_text
from .models import (
    AnswerOption,
    Book,
    Category,
    Favorite,
    Notification,
    Question,
    Quiz,
    QuizAttempt,
    ReadingEvent,
    ReadingProgress,
    User,
)
from .search import STOPWORDS, search_books, tokenize, _token_score

# Curated verified Ziyouz direct-PDF classics for instant local/API resolution
CURATED_ZIYOUZ_BOOKS = [
    {
        'title': "O‘tkan kunlar (roman)",
        'author': "Abdulla Qodiriy",
        'subject': "O‘zbek adabiyoti",
        'pdf': "https://n.ziyouz.com/books/uzbek_nasri/Abdulla%20Qodiriy.%20O'tkan%20kunlar%20(roman).pdf",
        'url': "https://n.ziyouz.com/kutubxona/category/41-o-zbek-nasri",
    },
    {
        'title': "Mehrobdan chayon (roman)",
        'author': "Abdulla Qodiriy",
        'subject': "O‘zbek adabiyoti",
        'pdf': "https://n.ziyouz.com/books/uzbek_nasri/Abdulla%20Qodiriy.%20Mehrobdan%20chayon%20(roman).pdf",
        'url': "https://n.ziyouz.com/kutubxona/category/41-o-zbek-nasri",
    },
    {
        'title': "Sarob (roman)",
        'author': "Abdulla Qahhor",
        'subject': "O‘zbek adabiyoti",
        'pdf': "https://n.ziyouz.com/books/uzbek_nasri/Abdulla%20Qahhor.%20Sarob%20(roman).pdf",
        'url': "https://n.ziyouz.com/kutubxona/category/41-o-zbek-nasri",
    },
    {
        'title': "Navoiy (roman)",
        'author': "Oybek",
        'subject': "O‘zbek adabiyoti",
        'pdf': "https://n.ziyouz.com/books/uzbek_nasri/Oybek.%20Navoiy%20(roman).pdf",
        'url': "https://n.ziyouz.com/kutubxona/category/41-o-zbek-nasri",
    },
    {
        'title': "Qutlug‘ qon (roman)",
        'author': "Oybek",
        'subject': "O‘zbek adabiyoti",
        'pdf': "https://n.ziyouz.com/books/uzbek_nasri/Oybek.%20Qutlug'%20qon%20(roman).pdf",
        'url': "https://n.ziyouz.com/kutubxona/category/41-o-zbek-nasri",
    },
    {
        'title': "Yulduzli tunlar (Bobur) (roman)",
        'author': "Pirimqul Qodirov",
        'subject': "O‘zbek adabiyoti",
        'pdf': "https://n.ziyouz.com/books/uzbek_nasri/Pirimqul%20Qodirov.%20Yulduzli%20tunlar%20(roman).pdf",
        'url': "https://n.ziyouz.com/kutubxona/category/41-o-zbek-nasri",
    },
    {
        'title': "Avlodlar dovoni (Humoyun va Akbar)",
        'author': "Pirimqul Qodirov",
        'subject': "O‘zbek adabiyoti",
        'pdf': "https://n.ziyouz.com/books/uzbek_nasri/Pirimqul%20Qodirov.%20Avlodlar%20dovoni%20(roman).pdf",
        'url': "https://n.ziyouz.com/kutubxona/category/41-o-zbek-nasri",
    },
    {
        'title': "Ulug‘bek xazinasi (roman)",
        'author': "Odil Yoqubov",
        'subject': "O‘zbek adabiyoti",
        'pdf': "https://n.ziyouz.com/books/uzbek_nasri/Odil%20Yoqubov.%20Ulug'bek%20xazinasi%20(roman).pdf",
        'url': "https://n.ziyouz.com/kutubxona/category/41-o-zbek-nasri",
    },
    {
        'title': "Otamdan qolgan dalalar (roman)",
        'author': "Tog‘ay Murod",
        'subject': "O‘zbek adabiyoti",
        'pdf': "https://n.ziyouz.com/books/uzbek_nasri/Tog'ay%20Murod.%20Otamdan%20qolgan%20dalalar%20(roman).pdf",
        'url': "https://n.ziyouz.com/kutubxona/category/41-o-zbek-nasri",
    },
    {
        'title': "Odam bo‘lish qiyin (roman)",
        'author': "O‘lmas Umarbekov",
        'subject': "O‘zbek adabiyoti",
        'pdf': "https://n.ziyouz.com/books/uzbek_nasri/O'lmas%20Umarbekov.%20Odam%20bo'lish%20qiyin%20(roman).pdf",
        'url': "https://n.ziyouz.com/kutubxona/category/41-o-zbek-nasri",
    },
    {
        'title': "Shum bola (qissa)",
        'author': "G‘afur G‘ulom",
        'subject': "O‘zbek adabiyoti",
        'pdf': "https://n.ziyouz.com/books/uzbek_nasri/G'afur%20G'ulom.%20Shum%20bola%20(qissa).pdf",
        'url': "https://n.ziyouz.com/kutubxona/category/41-o-zbek-nasri",
    },
    {
        'title': "Sariq devni minib (roman)",
        'author': "Xudoyberdi To‘xtaboyev",
        'subject': "Bolalar adabiyoti",
        'pdf': "https://n.ziyouz.com/books/bolalar_kutubxonasi/Xudoyberdi%20To'xtaboyev.%20Sariq%20devni%20minib%20(roman).pdf",
        'url': "https://n.ziyouz.com/kutubxona/category/17-bolalar-kutubxonasi",
    },
    {
        'title': "Boburnoma",
        'author': "Zahiriddin Muhammad Bobur",
        'subject': "Mumtoz adabiyot / Tarix",
        'pdf': "https://n.ziyouz.com/books/uzbek_mumtoz_adabiyoti/Zahiriddin%20Muhammad%20Bobur.%20Boburnoma.pdf",
        'url': "https://n.ziyouz.com/kutubxona/category/39-o-zbek-mumtoz-adabiyoti",
    },
    {
        'title': "Xamsa: Farhod va Shirin",
        'author': "Alisher Navoiy",
        'subject': "Mumtoz adabiyot",
        'pdf': "https://n.ziyouz.com/books/alisher_navoiy_asarlari/Alisher%20Navoiy.%20Xamsa.%20Farhod%20va%20Shirin%20(nasriy%20bayoni).pdf",
        'url': "https://n.ziyouz.com/kutubxona/category/40-alisher-navoiy-asarlari",
    },
    {
        'title': "Alpomish (o‘zbek xalq dostoni)",
        'author': "Fozil Yo‘ldosh o‘g‘li",
        'subject': "Folklor",
        'pdf': "https://n.ziyouz.com/books/uzbek_xalq_ogzaki_ijodi/Fozil%20Yo'ldosh%20o'g'li.%20Alpomish%20(doston).%201-qism.pdf",
        'url': "https://n.ziyouz.com/kutubxona/category/38-o-zbek-xalq-og-zaki-ijodi",
    },
    {
        'title': "Asrga tatigulik kun (roman)",
        'author': "Chingiz Aytmatov",
        'subject': "Jahon adabiyoti",
        'pdf': "https://n.ziyouz.com/books/jahon_nasri/Chingiz%20Aytmatov.%20Qiyomat.%20Asrga%20tatigulik%20kun%20(romanlar,%201989).pdf",
        'url': "https://n.ziyouz.com/kutubxona/category/14-jahon-nasri",
    },
]

_ZIYOUZ_INDEX_CACHE = None
_ZIYOUZ_BY_ID_CACHE = None


def _classify_ziyouz_bucket(subject):
    low = (subject or '').lower()
    if any(k in low for k in ('matematika', 'fizika', 'aniq fanlar', 'axborot texnologiya', 'texnika', 'statistika', 'geodeziya')):
        return 'aniq'
    if any(k in low for k in ('kimyo', 'biologiya', 'tabiiy fanlar', 'geografiya', 'ekologiya', 'tibbiyot', 'qishloq xo')):
        return 'tabiiy'
    if any(k in low for k in ('huquq', 'iqtisod', 'pedagogika', 'falsafa', 'axloq', 'ma’naviyat', 'publitsistika', 'prezident', 'sport', 'jismoniy tarbiya', 'ilmiy kitaplar', 'ilimiy kitaplar', 'turli mavzu', 'pazandalik', 'кулинария')):
        return 'ijtimoiy'
    if any(k in low for k in ('tillar va lug', 'lug‘atlar va ensiklopediya', 'словари', 'tarjima', 'in english')):
        return 'tillar'
    if any(k in low for k in ('jurnal', 'solnoma', 'letopis', 'yilnoma', 'bibliografik', 'sovet o‘zbekiston kitobi', 'молодая смена', 'звезда востока')):
        return 'jurnallar'
    if any(k in low for k in ('tarix', 'tariyx', 'og‘zaki ijod', 'folklor', 'устное народное', 'eski o‘zbek', 'tasavvuf', 'arxeolog', 'предков', 'мыслителей', 'hikmatlar', 'me’morchilik', 'san’at', 'musiqa', 'hunarmad')):
        return 'tarix'
    return 'badiiy'


def _db_category_bucket(cat_name):
    low = (cat_name or '').lower()
    if 'aniq' in low:
        return 'aniq'
    if 'tabiiy' in low:
        return 'tabiiy'
    if 'ijtimoiy' in low:
        return 'ijtimoiy'
    if 'til' in low:
        return 'tillar'
    if 'tarix' in low:
        return 'tarix'
    if 'ustoz' in low or 'o‘qituvchi' in low:
        return 'teacher'
    if 'jurnal' in low:
        return 'jurnallar'
    return 'badiiy'


def _get_ziyouz_index():
    global _ZIYOUZ_INDEX_CACHE, _ZIYOUZ_BY_ID_CACHE
    if _ZIYOUZ_INDEX_CACHE is None:
        idx_path = Path(__file__).resolve().parent / 'data' / 'ziyouz_books.json'
        try:
            items = json.loads(idx_path.read_text(encoding='utf-8'))
        except Exception:
            items = []
        by_id = {}
        for it in items:
            hay = f"{it.get('full_name', '')} {it.get('subject', '')}".lower()
            it['_hay'] = hay
            it['_tokens'] = frozenset(tokenize(hay))
            it['_title_l'] = (it.get('title') or '').lower().strip()
            it['_bucket'] = _classify_ziyouz_bucket(it.get('subject', ''))
            if it.get('id'):
                by_id[str(it['id'])] = it
        _PRIORITY_SUBJ = {
            'O‘zbek nasri': 0,
            'Jahon adabiyoti': 1,
            'Alisher Navoiy': 2,
            'Matematika': 3,
            'Fizika': 4,
            'Tarix': 5,
            'Mumtoz adabiyot': 6,
            'Biologiya': 7,
            'Kimyo': 8,
            'Tillar va lug‘atlar': 9,
            'O‘zbek zamonaviy she’riyati': 10,
            'Pedagogika va falsafa': 11,
            'Iqtisodiyot': 12,
            'Huquq va jamiyat': 13,
            'Tibbiyot': 14,
            'Geografiya': 15,
            'Aloqa va axborot texnologiyalari': 16,
            'Bolalar adabiyoti': 17,
        }
        items.sort(key=lambda x: (_PRIORITY_SUBJ.get(x.get('subject', ''), 50), x.get('subject', ''), x.get('full_name', '')))
        _ZIYOUZ_INDEX_CACHE = items
        _ZIYOUZ_BY_ID_CACHE = by_id
    return _ZIYOUZ_INDEX_CACHE, _ZIYOUZ_BY_ID_CACHE


def _search_ziyouz_index(query, limit=60, exclude_titles=None, exclude_urls=None, bucket=None, subject=None):
    items, _ = _get_ziyouz_index()
    q_tokens = tokenize(query)
    if not q_tokens or not items:
        return []
    q_lower = ' '.join(query.lower().split())
    excl_titles = {t.lower().strip() for t in (exclude_titles or ())}
    excl_urls = {u.strip() for u in (exclude_urls or ()) if u}
    subj_l = (subject or '').lower().strip()
    scored = []
    min_hits = len(q_tokens) if len(q_tokens) <= 2 else max(2, int(len(q_tokens) * 0.65))
    for item in items:
        if bucket and item.get('_bucket') != bucket:
            continue
        if subj_l and (item.get('subject') or '').lower().strip() != subj_l:
            continue
        if item.get('_title_l') in excl_titles or item.get('url', '').strip() in excl_urls:
            continue
        item_tokens = item.get('_tokens') or ()
        if not item_tokens:
            continue
        hay = item.get('_hay', '')
        total = 0.0
        matched = 0
        for qt in q_tokens:
            if qt in item_tokens:
                matched += 1
                total += 1.5
            elif len(qt) >= 3 and qt in hay:
                matched += 1
                total += 1.15
            else:
                best = 0.0
                for w in item_tokens:
                    if w[:1] != qt[:1] and len(w) > 3:
                        continue
                    s = _token_score(qt, w)
                    if s > best:
                        best = s
                        if best >= 0.95:
                            break
                if best >= 0.78:
                    matched += 1
                    total += best
        if matched >= min_hits:
            if q_lower and q_lower in hay:
                total += 3.0
            scored.append((total, item))
    scored.sort(key=lambda pair: -pair[0])
    if limit is None:
        return [pair[1] for pair in scored]
    return [pair[1] for pair in scored[:limit]]


def legacy_index(request):
    return render(request, 'catalog/legacy_index.html')


def home(request):
    has_catalog_filter = bool(
        request.GET.get('q')
        or request.GET.get('category')
        or request.GET.get('subject')
        or request.GET.get('language')
        or request.GET.get('page')
        or request.GET.get('browse')
        or (request.GET.get('guest') == '1')
    )

    if request.user.is_authenticated:
        show_auth_portal = False
    elif has_catalog_filter:
        show_auth_portal = False
    else:
        # Default for unauthenticated visitors on plain '/' is ALWAYS the dedicated Auth Portal
        request.session.pop('guest_mode', None)
        show_auth_portal = True
    auth_tab = request.GET.get('tab', 'login')
    auth_error = None

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'login':
            u_name = request.POST.get('username', '').strip()
            p_word = request.POST.get('password', '')
            user = authenticate(request, username=u_name, password=p_word)
            if user is not None and user.is_active:
                login(request, user)
                messages.success(request, f'Xush kelibsiz, {user.get_full_name() or user.username}!')
                return redirect('home')
            else:
                auth_error = 'Login yoki parol noto‘g‘ri kiritildi.'
                auth_tab = 'login'
                show_auth_portal = True
        elif action == 'register':
            u_name = request.POST.get('username', '').strip()
            p_word = request.POST.get('password', '')
            p_confirm = request.POST.get('password_confirm', '')
            f_name = request.POST.get('first_name', '').strip()
            l_name = request.POST.get('last_name', '').strip()
            if ' ' in f_name and not l_name:
                parts = f_name.split(' ', 1)
                f_name = parts[0]
                l_name = parts[1]

            if not u_name or not p_word:
                auth_error = 'Barcha majburiy maydonlarni to‘ldiring.'
                auth_tab = 'register'
                show_auth_portal = True
            elif p_confirm and p_word != p_confirm:
                auth_error = 'Kiritilgan parollar bir-biriga mos kelmadi.'
                auth_tab = 'register'
                show_auth_portal = True
            elif len(p_word) < 6:
                auth_error = 'Parol uzunligi kamida 6 ta belgidan iborat bo‘lishi kerak.'
                auth_tab = 'register'
                show_auth_portal = True
            elif User.objects.filter(username__iexact=u_name).exists():
                auth_error = 'Ushbu login band. Iltimos, boshqa login tanlang.'
                auth_tab = 'register'
                show_auth_portal = True
            else:
                user = User.objects.create_user(
                    username=u_name,
                    password=p_word,
                    first_name=f_name,
                    last_name=l_name,
                    role='student',
                    points=10,
                )
                Notification.objects.create(
                    user=user,
                    title='Raqamli kutubxonaga xush kelibsiz!',
                    message='Ro‘yxatdan o‘tganingiz uchun sizga +10 faollik balli taqdim etildi.',
                    url=reverse('leaderboard'),
                )
                login(request, user)
                messages.success(request, f'Xush kelibsiz, {user.get_full_name() or user.username}! Siz muvaffaqiyatli ro‘yxatdan o‘tdingiz (+10 ball).')
                return redirect('home')
        elif action == 'demo':
            demo_user = request.POST.get('demo_username', 'jasur_beruniy').strip()
            user = User.objects.filter(username=demo_user, is_active=True).first()
            if not user:
                user = User.objects.filter(is_active=True).first()
            if user:
                login(request, user)
                messages.success(request, f'Tizimga kirdingiz: {user.username}')
                return redirect('home')
        elif action == 'guest':
            request.session['guest_mode'] = True
            return redirect('/?guest=1')

    query = request.GET.get('q', '').strip()
    subject = request.GET.get('subject', '').strip()
    language = request.GET.get('language', '').strip()
    category_id = request.GET.get('category', '').strip()
    sort_by = request.GET.get('sort', '').strip()

    all_db_qs = Book.objects.filter(approved=True).select_related('category')
    db_titles = {b.title.lower().strip() for b in all_db_qs}
    db_urls = {b.external_url.strip() for b in all_db_qs if b.external_url}
    z_items, _ = _get_ziyouz_index()
    z_unique_items = [
        it for it in z_items
        if it.get('_title_l') not in db_titles and it.get('url', '').strip() not in db_urls
    ]
    z_bucket_counts = {}
    for it in z_unique_items:
        bk = it.get('_bucket', 'badiiy')
        z_bucket_counts[bk] = z_bucket_counts.get(bk, 0) + 1

    total_catalog_count = all_db_qs.count() + len(z_unique_items)

    raw_categories = list(
        Category.objects.annotate(
            approved_count=Count('books', filter=Q(books__approved=True))
        ).order_by('id')
    )
    cat_by_id = {str(c.id): c for c in raw_categories}
    categories = []
    for c in raw_categories:
        bk = _db_category_bucket(c.name)
        extra_cnt = 0 if bk == 'teacher' else z_bucket_counts.get(bk, 0)
        combined_cnt = c.approved_count + extra_cnt
        if combined_cnt > 0:
            categories.append({'id': c.id, 'name': c.name, 'approved_count': combined_cnt})
    if z_bucket_counts.get('jurnallar', 0) > 0:
        categories.append({
            'id': 'jurnallar',
            'name': 'Jurnallar va solnomalar',
            'approved_count': z_bucket_counts['jurnallar'],
        })

    books = all_db_qs
    bucket_filter = None
    if category_id == 'jurnallar':
        books = Book.objects.none()
        bucket_filter = 'jurnallar'
    elif category_id.isdigit():
        books = books.filter(category_id=int(category_id))
        sel_cat = cat_by_id.get(category_id)
        if sel_cat:
            bucket_filter = _db_category_bucket(sel_cat.name)

    if subject:
        books = books.filter(subject__iexact=subject)
    if language:
        books = books.filter(language__iexact=language)

    if sort_by == 'popular':
        books = books.order_by('-view_count', '-download_count', '-id')
    elif sort_by == 'downloads':
        books = books.order_by('-download_count', '-view_count', '-id')
    elif sort_by == 'newest':
        books = books.order_by('-created_at', '-id')

    if query:
        books = search_books(books, query)

    db_list = list(books)

    remote_list = []
    lang_allows_ziyouz = not language or 'o‘zbek' in language.lower() or "o'zbek" in language.lower()
    if bucket_filter != 'teacher' and lang_allows_ziyouz:
        if query:
            remote_list = _search_ziyouz_index(
                query,
                limit=None,
                exclude_titles=db_titles,
                exclude_urls=db_urls,
                bucket=bucket_filter,
                subject=subject,
            )
        else:
            subj_l = subject.lower().strip()
            remote_list = [
                it for it in z_unique_items
                if (not bucket_filter or it.get('_bucket') == bucket_filter)
                and (not subj_l or (it.get('subject') or '').lower().strip() == subj_l)
            ]

    combined_items = [('db', b) for b in db_list] + [('remote', rb) for rb in remote_list]
    paginator = Paginator(combined_items, 24)
    page_obj = paginator.get_page(request.GET.get('page'))
    page_books = [item for kind, item in page_obj.object_list if kind == 'db']
    remote_books = [item for kind, item in page_obj.object_list if kind == 'remote']
    page_items = list(paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1))

    favorites = (
        set(Favorite.objects.filter(user=request.user).values_list('book_id', flat=True))
        if request.user.is_authenticated
        else set()
    )
    subjects = (
        Book.objects.filter(approved=True)
        .exclude(subject='')
        .values_list('subject', flat=True)
        .distinct()
        .order_by('subject')
    )
    languages = (
        Book.objects.filter(approved=True)
        .values_list('language', flat=True)
        .distinct()
        .order_by('language')
    )
    top_readers = (
        User.objects.filter(role='student')
        .order_by('-points', '-id')[:5]
    )

    return render(
        request,
        'catalog/home.html',
        {
            'books': page_books,
            'remote_books': remote_books,
            'page_obj': page_obj,
            'page_items': page_items,
            'ellipsis_marker': paginator.ELLIPSIS,
            'query': query,
            'favorites': favorites,
            'categories': categories,
            'subjects': subjects,
            'languages': languages,
            'selected_subject': subject,
            'selected_language': language,
            'selected_category': category_id,
            'selected_sort': sort_by,
            'featured_books': Book.objects.filter(approved=True, featured=True).select_related('category')[:4],
            'teacher_books': Book.objects.filter(approved=True, is_teacher_book=True).select_related('category')[:4],
            'teacher_books_count': Book.objects.filter(approved=True, is_teacher_book=True).count(),
            'book_count': total_catalog_count,
            'filtered_count': paginator.count,
            'quiz_count': Quiz.objects.filter(is_published=True).count(),
            'reader_count': User.objects.filter(role='student').count(),
            'top_readers': top_readers,
            'show_auth_portal': show_auth_portal,
            'auth_tab': auth_tab,
            'auth_error': auth_error,
        },
    )


def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.role = 'student'
        user.points = 10  # Welcome bonus points
        user.save()
        Notification.objects.create(
            user=user,
            title='Raqamli kutubxonaga xush kelibsiz!',
            message='Ro‘yxatdan o‘tganingiz uchun sizga +10 boshlang‘ich faollik balli taqdim etildi. Kitob o‘qing va testlarni topshirib reytingda ko‘tariling!',
            url=reverse('leaderboard'),
        )
        login(request, user)
        messages.success(request, 'Hisobingiz yaratildi (+10 bonus ball). Raqamli kutubxonaga xush kelibsiz!')
        return redirect('dashboard')
    return render(
        request,
        'catalog/form_page.html',
        {
            'form': form,
            'title': 'Ro‘yxatdan o‘tish',
            'subtitle': 'Kutubxona xizmatlaridan foydalanish va reytingda qatnashish uchun hisob yarating.',
        },
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    redirect_target = (
        request.POST.get('next')
        or request.POST.get('redirectURL')
        or request.GET.get('redirectURL')
        or request.GET.get('next')
        or ''
    )
    error = None
    if request.method == 'POST':
        if request.POST.get('action') == 'register':
            u_name = request.POST.get('username', '').strip()
            p_word = request.POST.get('password', '')
            p_confirm = request.POST.get('password_confirm', '')
            f_name = request.POST.get('first_name', '').strip()
            l_name = request.POST.get('last_name', '').strip()
            if ' ' in f_name and not l_name:
                parts = f_name.split(' ', 1)
                f_name = parts[0]
                l_name = parts[1]

            if not u_name or not p_word:
                error = 'Barcha majburiy maydonlarni to‘ldiring.'
            elif p_confirm and p_word != p_confirm:
                error = 'Kiritilgan parollar bir-biriga mos kelmadi.'
            elif len(p_word) < 6:
                error = 'Parol uzunligi kamida 6 ta belgidan iborat bo‘lishi kerak.'
            elif User.objects.filter(username__iexact=u_name).exists():
                error = 'Ushbu login band. Iltimos, boshqa login tanlang.'
            else:
                user = User.objects.create_user(
                    username=u_name,
                    password=p_word,
                    first_name=f_name,
                    last_name=l_name,
                    role='student',
                    points=10,
                )
                Notification.objects.create(
                    user=user,
                    title='Raqamli kutubxonaga xush kelibsiz!',
                    message='Ro‘yxatdan o‘tganingiz uchun sizga +10 boshlang‘ich ball taqdim etildi.',
                    url=reverse('leaderboard'),
                )
                login(request, user)
                messages.success(request, f'Xush kelibsiz, {user.get_full_name() or user.username}! Siz muvaffaqiyatli ro‘yxatdan o‘tdingiz.')
                return redirect('home')

        elif request.POST.get('oneid_login') == '1' or request.POST.get('action') == 'demo':
            demo_username = request.POST.get('oneid_role') or request.POST.get('demo_username', 'admin')
            demo_username = (demo_username or 'admin').strip()
            user = User.objects.filter(username=demo_username, is_active=True).first()
            if user is None:
                user = User.objects.filter(is_active=True).order_by('-is_superuser', 'id').first()
            if user is not None:
                login(request, user)
                if url_has_allowed_host_and_scheme(
                    redirect_target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
                ):
                    return redirect(redirect_target)
                return redirect('home')
        user = authenticate(
            request,
            username=request.POST.get('username', '').strip(),
            password=request.POST.get('password', ''),
        )
        if user is not None and user.is_active:
            login(request, user)
            if url_has_allowed_host_and_scheme(
                redirect_target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return redirect(redirect_target)
            return redirect('home')
        error = 'Login yoki parol noto‘g‘ri.'
    return render(
        request,
        'catalog/login.html',
        {
            'error': error,
            'next': redirect_target,
            'redirectURL': redirect_target or '/',
            'show_auth_portal': True,
        },
    )


def logout_view(request):
    request.session.flush()
    logout(request)
    messages.success(request, 'Tizimdan muvaffaqiyatli chiqdingiz.')
    return redirect('home')




def book_detail(request, pk):
    book = get_object_or_404(Book.objects.select_related('category'), pk=pk, approved=True)
    Book.objects.filter(pk=pk).update(view_count=F('view_count') + 1)
    book.view_count += 1
    ReadingEvent.objects.create(
        user=request.user if request.user.is_authenticated else None,
        book=book,
        event_type='open',
    )
    progress = (
        ReadingProgress.objects.filter(user=request.user, book=book).first()
        if request.user.is_authenticated
        else None
    )
    is_favorite = (
        request.user.is_authenticated
        and Favorite.objects.filter(user=request.user, book=book).exists()
    )
    related_books = (
        Book.objects.filter(approved=True)
        .exclude(pk=book.pk)
        .filter(Q(subject__iexact=book.subject) | Q(category=book.category))
        .select_related('category')[:4]
    )
    if not related_books:
        related_books = Book.objects.filter(approved=True).exclude(pk=book.pk).select_related('category')[:4]

    return render(
        request,
        'catalog/book_detail.html',
        {
            'book': book,
            'progress': progress,
            'is_favorite': is_favorite,
            'related_books': related_books,
        },
    )


@login_required
@xframe_options_sameorigin
def book_pdf(request, pk):
    book = get_object_or_404(Book, pk=pk, approved=True)
    Book.objects.filter(pk=pk).update(view_count=F('view_count') + 1)
    if request.user.is_authenticated:
        ReadingEvent.objects.create(user=request.user, book=book, event_type='open')
        progress, _ = ReadingProgress.objects.get_or_create(user=request.user, book=book)
    else:
        progress = None
    if book.pdf_file:
        return render(
            request,
            'catalog/reader.html',
            {
                'book': book,
                'progress': progress,
                'pdf_source_url': reverse('book_pdf_file', args=[book.pk]),
            },
        )
    if book.external_url:
        ext = book.external_url.strip()
        is_pdf_source = ext.lower().split('?')[0].endswith('.pdf') or (
            'ziyouz.com' in ext.lower() and 'download=' in ext.lower()
        )
        if is_pdf_source and _host_ok(ext):
            proxy_url = f"{reverse('pdf_proxy')}?url={urllib.parse.quote(ext)}"
            return render(
                request,
                'catalog/reader.html',
                {
                    'book': book,
                    'progress': progress,
                    'pdf_source_url': proxy_url,
                    'external_direct_url': ext,
                },
            )
        return redirect(ext)
    raise Http404('Bu kitob uchun PDF hali yuklanmagan.')


@xframe_options_sameorigin
def book_pdf_file(request, pk):
    book = get_object_or_404(Book, pk=pk, approved=True)
    if not book.pdf_file:
        if book.external_url:
            ext = book.external_url.strip()
            if ext.lower().split('?')[0].endswith('.pdf') and _host_ok(ext):
                return redirect(f"{reverse('pdf_proxy')}?url={urllib.parse.quote(ext)}")
            return redirect(book.external_url)
        raise Http404('Bu kitob uchun PDF hali yuklanmagan.')
    safe_name = (
        ''.join(ch for ch in book.title if ch.isalnum() or ch in (' ', '-', '_')).strip()[:100]
        or 'kitob'
    )
    return FileResponse(
        book.pdf_file.open('rb'),
        content_type='application/pdf',
        as_attachment=False,
        filename=f'{safe_name}.pdf',
    )


def download_book_file(request, pk):
    book = get_object_or_404(Book, pk=pk, approved=True)
    if not book.pdf_file and not book.external_url:
        raise Http404('Bu kitob uchun fayl yuklanmagan.')

    Book.objects.filter(pk=pk).update(download_count=F('download_count') + 1)
    if request.user.is_authenticated:
        already_downloaded = ReadingEvent.objects.filter(
            user=request.user, book=book, event_type='download'
        ).exists()
        ReadingEvent.objects.create(user=request.user, book=book, event_type='download')
        if not already_downloaded:
            User.objects.filter(pk=request.user.pk).update(points=F('points') + 5)

    if not book.pdf_file and book.external_url:
        ext = book.external_url.strip()
        is_pdf_source = ext.lower().split('?')[0].endswith('.pdf') or (
            'ziyouz.com' in ext.lower() and 'download=' in ext.lower()
        )
        if is_pdf_source and _host_ok(ext):
            safe_name = ''.join(ch for ch in book.title if ch.isalnum() or ch in (' ', '-', '_')).strip()[:80] or 'kitob'
            return redirect(f"{reverse('pdf_proxy')}?url={urllib.parse.quote(ext)}&download=1&filename={urllib.parse.quote(safe_name + '.pdf')}")
        return redirect(ext)

    safe_name = (
        ''.join(ch for ch in book.title if ch.isalnum() or ch in (' ', '-', '_')).strip()[:80]
        or 'kitob'
    )
    return FileResponse(
        book.pdf_file.open('rb'),
        as_attachment=True,
        filename=f'{safe_name}.pdf',
    )


def _render_qr_png(target_url, download_filename=None):
    import qrcode

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(target_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#002f6c', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    response = HttpResponse(buf.getvalue(), content_type='image/png')
    if download_filename:
        response['Content-Disposition'] = f'attachment; filename="{download_filename}"'
    return response


def book_qrcode(request, pk):
    book = get_object_or_404(Book, pk=pk, approved=True)
    target_url = request.build_absolute_uri(reverse('book_detail', args=[book.pk]))
    download_name = None
    if request.GET.get('download'):
        safe_name = (
            ''.join(c for c in book.title if c.isalnum() or c in (' ', '-', '_')).strip()[:40]
            or 'kitob'
        )
        download_name = f'QR-{safe_name}.png'
    return _render_qr_png(target_url, download_filename=download_name)


def certificate_qrcode(request, pk):
    attempt = get_object_or_404(QuizAttempt, pk=pk)
    target_url = request.build_absolute_uri(reverse('certificate_view', args=[attempt.pk]))
    return _render_qr_png(target_url)


@login_required
@require_POST
def save_progress(request, pk):
    book = get_object_or_404(Book, pk=pk, approved=True)
    try:
        data = json.loads(request.body or '{}')
        page = max(1, min(int(data.get('page', 1)), 1000000))
        total = max(0, min(int(data.get('total', 0)), 1000000))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'Noto‘g‘ri ma’lumot'}, status=400)

    progress, created = ReadingProgress.objects.get_or_create(user=request.user, book=book)
    old_page = progress.current_page
    progress.current_page = page
    progress.total_pages = total
    progress.save(update_fields=['current_page', 'total_pages', 'updated_at'])

    if created:
        User.objects.filter(pk=request.user.pk).update(points=F('points') + 10)
    elif page > old_page:
        User.objects.filter(pk=request.user.pk).update(points=F('points') + 2)

    return JsonResponse({'ok': True, 'page': progress.current_page, 'percent': progress.percent})


@login_required
@require_POST
def toggle_favorite(request, pk):
    book = get_object_or_404(Book, pk=pk, approved=True)
    obj, created = Favorite.objects.get_or_create(user=request.user, book=book)
    if not created:
        obj.delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
        return JsonResponse({'ok': True, 'is_favorite': created, 'favorite': created, 'book_id': book.pk})
    messages.success(
        request,
        'Kitob sevimlilarga qo‘shildi.' if created else 'Kitob sevimlilardan olib tashlandi.',
    )
    next_url = request.POST.get('next') or 'home'
    return redirect(
        next_url
        if url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        )
        else 'home'
    )


@login_required
def favorites(request):
    books = Book.objects.filter(favorites__user=request.user, approved=True).select_related('category')
    return render(request, 'catalog/favorites.html', {'books': books})


def _load_uz_provinces():
    provinces_file = Path(__file__).resolve().parent / 'static' / 'catalog' / 'uzedu' / 'uz_provinces.json'
    try:
        data = json.loads(provinces_file.read_text(encoding='utf-8'))
        return data.get('provinces', [])
    except Exception:
        return []


def dashboard(request):
    is_auth = request.user.is_authenticated
    user = request.user if is_auth else None

    # Handle Profile Update
    if request.method == 'POST' and request.POST.get('action') == 'update_profile':
        if not is_auth:
            return redirect('login')
        f_name = request.POST.get('first_name', '').strip()
        l_name = request.POST.get('last_name', '').strip()
        group_name = request.POST.get('group_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        if f_name:
            user.first_name = f_name
        if l_name:
            user.last_name = l_name
        user.group_name = group_name
        user.phone = phone
        if 'avatar' in request.FILES:
            user.avatar = request.FILES['avatar']
        user.save()
        messages.success(request, 'Profil ma’lumotlari muvaffaqiyatli saqlandi.')
        return redirect('profile')

    progress = (
        ReadingProgress.objects.filter(user=user)
        .select_related('book')
        .order_by('-updated_at')[:8]
        if is_auth
        else []
    )
    fav_books = (
        Book.objects.filter(favorites__user=user, approved=True).select_related('category')[:8]
        if is_auth
        else []
    )
    attempts = (
        QuizAttempt.objects.filter(user=user)
        .select_related('quiz')
        .order_by('-created_at')[:10]
        if is_auth
        else []
    )
    notifications = user.notifications.filter(is_read=False)[:5] if is_auth else []
    rank = (
        User.objects.filter(role='student', points__gt=user.points).count() + 1
        if is_auth and user.role == 'student'
        else 1
    )

    total_books_db = Book.objects.filter(approved=True).count()
    teacher_books_db = Book.objects.filter(approved=True, is_teacher_book=True).count()
    pending_books_db = Book.objects.filter(approved=False).count()
    total_users_db = User.objects.count()
    total_quizzes_db = Quiz.objects.filter(is_published=True).count()
    z_items, _ = _get_ziyouz_index()
    total_catalog_db = total_books_db + max(0, len(z_items) - 9)

    is_admin_user = bool(is_auth and (user.role == 'librarian' or user.is_staff or user.is_superuser))
    req_ws = request.GET.get('workspace')
    if req_ws in ('admin', 'teacher', 'student') and (request.path in ('/dashboard', '/dashboard/') or is_admin_user or req_ws == 'student' or (req_ws == 'teacher' and is_auth and user.role == 'teacher')):
        active_workspace = req_ws
    elif is_admin_user:
        active_workspace = 'admin'
    elif is_auth and user.role == 'teacher':
        active_workspace = 'teacher'
    elif is_auth and user.role == 'student':
        active_workspace = 'student'
    else:
        active_workspace = 'admin' if request.path in ('/dashboard', '/dashboard/') else 'student'

    all_users = User.objects.all().order_by('-date_joined')
    students_count = User.objects.filter(role='student').count()
    teachers_count = User.objects.filter(role='teacher').count()
    admins_count = User.objects.filter(role='librarian').count()

    teacher_my_books = (
        Book.objects.filter(submitted_by=user).select_related('category').order_by('-created_at')
        if is_auth
        else []
    )
    if not teacher_my_books:
        teacher_my_books = Book.objects.filter(is_teacher_book=True).select_related('category').order_by('-created_at')[:10]

    teacher_quizzes = (
        Quiz.objects.filter(created_by=user).order_by('-created_at')
        if is_auth
        else []
    )
    if not teacher_quizzes:
        teacher_quizzes = Quiz.objects.filter(is_published=True).order_by('-created_at')[:8]

    all_books_admin = Book.objects.all().select_related('category', 'submitted_by').order_by('-created_at')
    all_attempts_feed = QuizAttempt.objects.select_related('user', 'quiz').order_by('-created_at')[:15]

    # Check whether to render the National Map Dashboard or the Clean User Profile
    if request.path in ('/dashboard', '/dashboard/'):
        raw_provinces = _load_uz_provinces()
        province_stats_preset = {
            'Xorazm viloyati': {'schools': 549, 'students': 368420, 'books': 4892450, 'coverage': 100.0, 'color_Var': 'var(--color-coverage-100)', 'is_home': True},
            'Qoraqalpog\u02bbiston Respublikasi': {'schools': 726, 'students': 354110, 'books': 4610200, 'coverage': 99.6, 'color_Var': 'var(--color-coverage-98)', 'is_home': False},
            'Toshkent shahri': {'schools': 352, 'students': 518900, 'books': 6840100, 'coverage': 100.0, 'color_Var': 'var(--color-coverage-100)', 'is_home': False},
            'Samarqand viloyati': {'schools': 1265, 'students': 782400, 'books': 9985000, 'coverage': 98.8, 'color_Var': 'var(--color-coverage-98)', 'is_home': False},
            'Farg\u02bbona viloyati': {'schools': 978, 'students': 712300, 'books': 9240000, 'coverage': 99.4, 'color_Var': 'var(--color-coverage-98)', 'is_home': False},
            'Andijon viloyati': {'schools': 768, 'students': 598400, 'books': 7710000, 'coverage': 99.1, 'color_Var': 'var(--color-coverage-98)', 'is_home': False},
            'Namangan viloyati': {'schools': 714, 'students': 544200, 'books': 7015000, 'coverage': 98.5, 'color_Var': 'var(--color-coverage-98)', 'is_home': False},
            'Buxoro viloyati': {'schools': 542, 'students': 339800, 'books': 4490000, 'coverage': 100.0, 'color_Var': 'var(--color-coverage-100)', 'is_home': False},
            'Qashqadaryo viloyati': {'schools': 1218, 'students': 685100, 'books': 8620000, 'coverage': 97.4, 'color_Var': 'var(--color-coverage-85)', 'is_home': False},
            'Surxondaryo viloyati': {'schools': 965, 'students': 552700, 'books': 6940000, 'coverage': 96.8, 'color_Var': 'var(--color-coverage-85)', 'is_home': False},
            'Toshkent viloyati': {'schools': 892, 'students': 539600, 'books': 6895000, 'coverage': 98.9, 'color_Var': 'var(--color-coverage-98)', 'is_home': False},
            'Navoiy viloyati': {'schools': 372, 'students': 198400, 'books': 2645000, 'coverage': 100.0, 'color_Var': 'var(--color-coverage-100)', 'is_home': False},
            'Jizzax viloyati': {'schools': 564, 'students': 279500, 'books': 3580000, 'coverage': 98.2, 'color_Var': 'var(--color-coverage-98)', 'is_home': False},
            'Sirdaryo viloyati': {'schools': 318, 'students': 168900, 'books': 2190000, 'coverage': 99.2, 'color_Var': 'var(--color-coverage-98)', 'is_home': False},
        }
        provinces = []
        for p in raw_provinces:
            st = province_stats_preset.get(
                p['name'],
                {'schools': 450, 'students': 290000, 'books': 3750000, 'coverage': 98.5, 'color_Var': 'var(--color-coverage-98)', 'is_home': False},
            )
            provinces.append({**p, **st})

        regional_rows = [
            {'code': '1733401', 'name': 'Urganch shahri (Beruniy litseyi)', 'schools': 38, 'students': 48620, 'books': 684920, 'per_student': '14.1', 'coverage': 100.0, 'badge': 'cov-100', 'is_active': True},
            {'code': '1733403', 'name': 'Xiva shahri', 'schools': 24, 'students': 22450, 'books': 312400, 'per_student': '13.9', 'coverage': 100.0, 'badge': 'cov-100', 'is_active': False},
            {'code': '1733217', 'name': 'Urganch tumani', 'schools': 56, 'students': 41890, 'books': 568400, 'per_student': '13.6', 'coverage': 99.6, 'badge': 'cov-98', 'is_active': False},
            {'code': '1733226', 'name': 'Xonqa tumani', 'schools': 52, 'students': 37640, 'books': 508200, 'per_student': '13.5', 'coverage': 99.4, 'badge': 'cov-98', 'is_active': False},
            {'code': '1733220', 'name': 'Hazorasp tumani', 'schools': 54, 'students': 38910, 'books': 521400, 'per_student': '13.4', 'coverage': 99.1, 'badge': 'cov-98', 'is_active': False},
            {'code': '1733212', 'name': 'Qo‘shko‘pir tumani', 'schools': 51, 'students': 35200, 'books': 468100, 'per_student': '13.3', 'coverage': 98.8, 'badge': 'cov-98', 'is_active': False},
            {'code': '1733230', 'name': 'Shovot tumani', 'schools': 49, 'students': 34180, 'books': 454600, 'per_student': '13.3', 'coverage': 98.7, 'badge': 'cov-98', 'is_active': False},
            {'code': '1733204', 'name': 'Bog‘ot tumani', 'schools': 47, 'students': 32750, 'books': 435900, 'per_student': '13.3', 'coverage': 98.5, 'badge': 'cov-98', 'is_active': False},
            {'code': '1733208', 'name': 'Gurlan tumani', 'schools': 46, 'students': 30840, 'books': 407100, 'per_student': '13.2', 'coverage': 98.3, 'badge': 'cov-98', 'is_active': False},
            {'code': '1733233', 'name': 'Yangiariq tumani', 'schools': 39, 'students': 24610, 'books': 324800, 'per_student': '13.2', 'coverage': 98.1, 'badge': 'cov-98', 'is_active': False},
            {'code': '1733236', 'name': 'Yangibozor tumani', 'schools': 33, 'students': 21330, 'books': 281630, 'per_student': '13.2', 'coverage': 97.9, 'badge': 'cov-85', 'is_active': False},
        ]

        grade_chart_bars = [
            {'label': '1-kurs (Aniq)', 'short': '1-A', 'students': 420, 'books': 6420, 'height_pct': 92, 'coverage': '100%'},
            {'label': '2-kurs (Aniq)', 'short': '2-A', 'students': 395, 'books': 6110, 'height_pct': 88, 'coverage': '100%'},
            {'label': '1-kurs (Tabiiy)', 'short': '1-T', 'students': 340, 'books': 5180, 'height_pct': 76, 'coverage': '99.4%'},
            {'label': '2-kurs (Tabiiy)', 'short': '2-T', 'students': 325, 'books': 4920, 'height_pct': 72, 'coverage': '99.1%'},
            {'label': '1-kurs (Xorijiy)', 'short': '1-X', 'students': 380, 'books': 5890, 'height_pct': 84, 'coverage': '100%'},
            {'label': '2-kurs (Xorijiy)', 'short': '2-X', 'students': 360, 'books': 5540, 'height_pct': 80, 'coverage': '99.7%'},
            {'label': 'Ijtimoiy-huquq', 'short': 'IJT', 'students': 290, 'books': 4350, 'height_pct': 65, 'coverage': '98.8%'},
            {'label': 'Xorijiy tillar kursi', 'short': 'TILLAR', 'students': 460, 'books': 7120, 'height_pct': 98, 'coverage': '100%'},
            {'label': 'Fond Kitoblari', 'short': 'PDF', 'students': 520, 'books': 8450, 'height_pct': 100, 'coverage': '100%'},
        ]

        language_rows = [
            {'id': 'uz', 'name': 'O‘zbek tili', 'flag': '_uz.svg', 'students': '318 450', 'books': '4 245 800', 'catalog_count': Book.objects.filter(approved=True, language='uz').count(), 'share': '86.4%'},
            {'id': 'ru', 'name': 'Rus tili', 'flag': '_ru.svg', 'students': '28 940', 'books': '386 200', 'catalog_count': Book.objects.filter(approved=True, language='ru').count(), 'share': '7.9%'},
            {'id': 'en', 'name': 'Ingliz tili kursi', 'flag': '_qg.svg', 'students': '14 620', 'books': '184 900', 'catalog_count': Book.objects.filter(approved=True, language='en').count(), 'share': '4.0%'},
            {'id': 'qq', 'name': 'Qoraqalpoq tili', 'flag': '_qq.svg', 'students': '3 850', 'books': '46 200', 'catalog_count': 0, 'share': '1.0%'},
            {'id': 'tm', 'name': 'Turkman tili', 'flag': '_tm.svg', 'students': '1 640', 'books': '19 680', 'catalog_count': 0, 'share': '0.4%'},
            {'id': 'kz', 'name': 'Qozoq tili', 'flag': '_kz.svg', 'students': '920', 'books': '9 670', 'catalog_count': 0, 'share': '0.3%'},
        ]

        return render(
            request,
            'catalog/dashboard.html',
            {
                'active_workspace': active_workspace,
                'all_users': all_users,
                'students_count': students_count,
                'teachers_count': teachers_count,
                'admins_count': admins_count,
                'teacher_my_books': teacher_my_books,
                'teacher_quizzes': teacher_quizzes,
                'all_attempts_feed': all_attempts_feed,
                'all_books_admin': all_books_admin,
                'progress': progress,
                'favorites': fav_books,
                'attempts': attempts,
                'notifications': notifications,
                'rank': rank,
                'total_books_read': ReadingProgress.objects.filter(user=user).count() if is_auth else 6,
                'total_certificates': QuizAttempt.objects.filter(user=user).exclude(certificate_code='').count() if is_auth else 3,
                'total_books_db': total_books_db,
                'teacher_books_db': teacher_books_db,
                'total_users_db': total_users_db,
                'total_quizzes_db': total_quizzes_db,
                'provinces': provinces,
                'regional_rows': regional_rows,
                'grade_chart_bars': grade_chart_bars,
                'language_rows': language_rows,
                'recent_books': Book.objects.filter(approved=True).select_related('category')[:8],
            },
        )

    # Otherwise render clean Profile page (for /profil/, /profile/, /kabinet/)
    if not is_auth:
        return redirect(f"{reverse('login')}?next={request.path}")

    return render(
        request,
        'catalog/profile.html',
        {
            'active_workspace': active_workspace,
            'all_users': all_users,
            'students_count': students_count,
            'teachers_count': teachers_count,
            'admins_count': admins_count,
            'teacher_my_books': teacher_my_books,
            'teacher_quizzes': teacher_quizzes,
            'all_quizzes_manage': Quiz.objects.annotate(num_questions=Count('questions')).order_by('-created_at'),
            'all_attempts_feed': all_attempts_feed,
            'all_books_admin': all_books_admin,
            'progress': progress,
            'favorites': fav_books,
            'attempts': attempts,
            'notifications': notifications,
            'rank': rank,
            'total_books_read': ReadingProgress.objects.filter(user=user).count(),
            'total_certificates': QuizAttempt.objects.filter(user=user).exclude(certificate_code='').count(),
            'total_books_db': total_books_db,
            'total_catalog_db': total_catalog_db,
            'teacher_books_db': teacher_books_db,
            'pending_books_db': pending_books_db,
            'total_users_db': total_users_db,
            'total_quizzes_db': total_quizzes_db,
        },
    )


def _admin_redirect_target(request, default_view='profile'):
    nxt = (request.POST.get('next') or request.GET.get('next') or '').strip()
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return f"{reverse(default_view)}?workspace=admin"


@login_required
def admin_add_user(request):
    if not (request.user.role == 'librarian' or request.user.is_staff or request.user.is_superuser):
        raise PermissionDenied
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        role = request.POST.get('role', 'student').strip()
        group_name = request.POST.get('group_name', '').strip()
        phone = request.POST.get('phone', '').strip()[:30]
        email = request.POST.get('email', '').strip()

        if not username or not password:
            messages.error(request, 'Login va parol kiritilishi shart!')
            return redirect(_admin_redirect_target(request, default_view='dashboard'))

        if User.objects.filter(username=username).exists():
            messages.error(request, f"'{username}' loginli foydalanuvchi tizimda allaqachon mavjud!")
            return redirect(_admin_redirect_target(request, default_view='dashboard'))

        user = User.objects.create(
            username=username,
            first_name=first_name,
            last_name=last_name,
            role=role if role in ('student', 'teacher', 'librarian') else 'student',
            group_name=group_name,
            phone=phone,
            email=email,
            is_staff=(role == 'librarian'),
        )
        user.set_password(password)
        user.save()
        messages.success(
            request,
            f"Yangi foydalanuvchi '{user.get_full_name() or user.username}' ({user.get_role_display()}) muvaffaqiyatli qo‘shildi!",
        )
    return redirect(_admin_redirect_target(request, default_view='dashboard'))


@login_required
def admin_edit_user(request, pk):
    if not (request.user.role == 'librarian' or request.user.is_staff or request.user.is_superuser):
        raise PermissionDenied
    if request.method == 'POST':
        target_user = get_object_or_404(User, pk=pk)
        new_username = request.POST.get('username', '').strip()
        new_password = request.POST.get('password', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        group_name = request.POST.get('group_name', '').strip()
        phone = request.POST.get('phone', '').strip()[:30]
        new_role = request.POST.get('role', target_user.role).strip()

        if not new_username:
            messages.error(request, 'Login bo‘sh bo‘lishi mumkin emas!')
            return redirect(_admin_redirect_target(request, default_view='profile'))

        if new_username != target_user.username and User.objects.filter(username=new_username).exists():
            messages.error(request, f"'{new_username}' logini allaqachon band!")
            return redirect(_admin_redirect_target(request, default_view='profile'))

        target_user.username = new_username
        target_user.first_name = first_name
        target_user.last_name = last_name
        target_user.group_name = group_name
        target_user.phone = phone

        if new_role in ('student', 'teacher', 'librarian'):
            if target_user.pk == request.user.pk and new_role != 'librarian' and not target_user.is_superuser:
                messages.error(request, 'O‘zingizning administrator huquqingizni olib tashlay olmaysiz.')
                return redirect(_admin_redirect_target(request, default_view='profile'))
            target_user.role = new_role
            if new_role == 'librarian':
                target_user.is_staff = True
            elif new_role in ('student', 'teacher') and not target_user.is_superuser:
                target_user.is_staff = False

        if new_password:
            if len(new_password) < 4:
                messages.error(request, 'Yangi parol kamida 4 ta belgidan iborat bo‘lishi kerak.')
                return redirect(_admin_redirect_target(request, default_view='profile'))
            target_user.set_password(new_password)

        target_user.save()
        messages.success(
            request,
            f"«{target_user.get_full_name() or target_user.username}» ma’lumotlari muvaffaqiyatli yangilandi!",
        )
    return redirect(_admin_redirect_target(request, default_view='profile'))


@login_required
def admin_toggle_user_active(request, pk):
    if not (request.user.role == 'librarian' or request.user.is_staff or request.user.is_superuser):
        raise PermissionDenied
    if request.method == 'POST':
        target_user = get_object_or_404(User, pk=pk)
        if target_user.pk == request.user.pk:
            messages.error(request, 'O‘z hisobingizni faolsizlantira olmaysiz!')
            return redirect(_admin_redirect_target(request, default_view='profile'))
        target_user.is_active = not target_user.is_active
        target_user.save(update_fields=['is_active'])
        state_lbl = 'faollashtirildi' if target_user.is_active else 'vaqtincha to‘xtatildi'
        messages.success(request, f"«{target_user.get_full_name() or target_user.username}» hisobi {state_lbl}.")
    return redirect(_admin_redirect_target(request, default_view='profile'))


@login_required
def admin_delete_user(request, pk):
    if not (request.user.role == 'librarian' or request.user.is_staff or request.user.is_superuser):
        raise PermissionDenied
    if request.method == 'POST':
        target_user = get_object_or_404(User, pk=pk)
        if target_user.pk == request.user.pk:
            messages.error(request, 'O‘z hisobingizni o‘chira olmaysiz!')
            return redirect(_admin_redirect_target(request, default_view='dashboard'))
        uname = target_user.get_full_name() or target_user.username
        target_user.delete()
        messages.success(request, f"Foydalanuvchi '{uname}' tizimdan muvaffaqiyatli o‘chirildi.")
    return redirect(_admin_redirect_target(request, default_view='dashboard'))


def _can_manage_content(user):
    return bool(
        user.is_authenticated
        and (user.role in ('teacher', 'librarian') or user.is_staff or user.is_superuser)
    )


@login_required
def admin_change_user_role(request, pk):
    if not (request.user.role == 'librarian' or request.user.is_staff or request.user.is_superuser):
        raise PermissionDenied
    if request.method == 'POST':
        target_user = get_object_or_404(User, pk=pk)
        new_role = request.POST.get('role', '').strip()
        if new_role in ('student', 'teacher', 'librarian'):
            target_user.role = new_role
            if new_role == 'librarian':
                target_user.is_staff = True
            elif new_role in ('student', 'teacher') and not target_user.is_superuser:
                target_user.is_staff = False
            target_user.save()
            role_labels = {
                'student': 'O‘quvchi',
                'teacher': 'Kutubxonachi',
                'librarian': 'Administrator',
            }
            messages.success(
                request,
                f"«{target_user.get_full_name() or target_user.username}» foydalanuvchisiga «{role_labels.get(new_role, new_role)}» roli tayinlandi!",
            )
    return redirect(_admin_redirect_target(request, default_view='dashboard'))


@login_required
def admin_delete_book(request, pk):
    if not _can_manage_content(request.user):
        raise PermissionDenied
    if request.method == 'POST':
        book = get_object_or_404(Book, pk=pk)
        title = book.title
        book.delete()
        messages.success(request, f"'{title}' kitobi fonddan muvaffaqiyatli o‘chirildi.")
    return redirect(_admin_redirect_target(request, default_view='dashboard'))


@login_required
def admin_approve_book(request, pk):
    if not _can_manage_content(request.user):
        raise PermissionDenied
    if request.method == 'POST':
        book = get_object_or_404(Book, pk=pk)
        book.approved = True
        book.save(update_fields=['approved'])
        messages.success(request, f"'{book.title}' kitobi tasdiqlandi va katalogga chiqarildi.")
    return redirect(_admin_redirect_target(request, default_view='profile'))


@login_required
def admin_toggle_teacher_book(request, pk):
    if not _can_manage_content(request.user):
        raise PermissionDenied
    if request.method == 'POST':
        book = get_object_or_404(Book, pk=pk)
        book.is_teacher_book = not book.is_teacher_book
        book.save(update_fields=['is_teacher_book'])
        if book.is_teacher_book:
            messages.success(request, f"'{book.title}' tanlangan qo‘llanmalar bo‘limiga qo‘shildi.")
        else:
            messages.success(request, f"'{book.title}' maxsus bo‘limdan olib tashlandi.")
    return redirect(_admin_redirect_target(request, default_view='profile'))


@login_required
def upload_book(request):
    if not _can_manage_content(request.user):
        raise PermissionDenied
    form = BookForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        book = form.save(commit=False)
        book.submitted_by = request.user
        book.approved = True
        book.save()

        # Extract real Page-1 title cover from uploaded PDF when no manual cover uploaded
        if not book.cover:
            cover_bytes = None
            if book.pdf_file:
                try:
                    with book.pdf_file.open('rb') as pf:
                        cover_bytes = render_pdf_cover_bytes(pf.read())
                except Exception:
                    cover_bytes = None
            elif book.external_url and _host_ok(book.external_url.strip()):
                try:
                    with _opener.open(urllib.request.Request(book.external_url.strip(), headers=_UA), timeout=12) as r:
                        raw = r.read(15 * 1024 * 1024)
                    cover_bytes = render_pdf_cover_bytes(raw)
                except Exception:
                    cover_bytes = None
            if cover_bytes:
                book.cover.save(f'title_{book.pk}.jpg', ContentFile(cover_bytes), save=True)

        messages.success(
            request,
            'Kitob muvaffaqiyatli qo‘shildi!' if book.approved else 'Kitob qabul qilindi. Moderator tasdiqlashidan keyin katalogda ko‘rinadi.',
        )
        return redirect('profile')
    return render(
        request,
        'catalog/form_page.html',
        {
            'form': form,
            'title': 'Kitob yuborish',
            'subtitle': 'Kitob ma’lumotlarini to‘ldiring. Muqova bo‘sh qolsa, PDF birinchi sahifasi avtomatik olinadi.',
        },
    )


def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Murojaatingiz yuborildi. Rahmat!')
        return redirect('contact')
    return render(
        request,
        'catalog/form_page.html',
        {
            'form': form,
            'title': 'Biz bilan bog‘lanish',
            'subtitle': 'Taklif va xabarlaringiz kutubxonani yaxshilashga yordam beradi.',
        },
    )


@login_required
def parse_quiz_import_api(request):
    if request.user.role not in ('teacher', 'librarian') and not request.user.is_staff and not request.user.is_superuser:
        raise PermissionDenied
    if request.method == 'GET' and request.GET.get('template') == '1':
        resp = HttpResponse(QUIZ_TEMPLATE_TEXT, content_type='text/plain; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="test_shabloni.txt"'
        return resp
    if request.method != 'POST':
        return JsonResponse({'error': 'POST so‘rovi talab qilinadi.'}, status=405)

    uploaded = request.FILES.get('file')
    raw_text = request.POST.get('raw_text', '')
    if uploaded:
        if uploaded.size > 5 * 1024 * 1024:
            return JsonResponse({'error': 'Fayl hajmi 5 MB dan oshmasligi kerak.'}, status=400)
        try:
            raw_text = extract_text_from_uploaded_file(uploaded)
        except Exception:
            return JsonResponse({'error': 'Faylni o‘qib bo‘lmadi (.txt, .docx, .csv yoki .json tanlang).'}, status=400)

    questions = parse_quiz_text(raw_text)
    if not questions:
        return JsonResponse(
            {'error': 'Savollar topilmadi. Namuna shablon formatini tekshiring.'},
            status=400,
        )
    return JsonResponse({'questions': questions, 'count': len(questions)})


@login_required
def create_quiz(request):
    if request.user.role not in ('teacher', 'librarian') and not request.user.is_staff and not request.user.is_superuser:
        raise PermissionDenied
    errors = []
    submitted_questions = None

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()[:200]
        subject = request.POST.get('subject', '').strip()[:100]
        description = request.POST.get('description', '').strip()[:3000]
        prepared = []
        drafts = []

        if not title:
            errors.append('Test nomini kiriting.')

        # Collect all dynamic question_<n> indices in order
        q_indices = []
        for key in request.POST.keys():
            m = _re.match(r'^question_(\d+)$', key)
            if m:
                q_indices.append(int(m.group(1)))
        q_indices = sorted(set(q_indices))

        for display_num, idx in enumerate(q_indices, start=1):
            text = request.POST.get(f'question_{idx}', '').strip()[:1000]
            opt_nums = []
            prefix = f'option_{idx}_'
            for key in request.POST.keys():
                if key.startswith(prefix):
                    tail = key[len(prefix):]
                    if tail.isdigit():
                        opt_nums.append(int(tail))
            opt_nums = sorted(set(opt_nums)) or [1, 2, 3, 4]
            options = [
                (opt_i, request.POST.get(f'option_{idx}_{opt_i}', '').strip()[:500])
                for opt_i in opt_nums
            ]
            nonempty = [(opt_i, val) for opt_i, val in options if val]
            correct = request.POST.get(f'correct_{idx}', '').strip()
            corr_int = int(correct) if correct.isdigit() else 0

            if not text and not nonempty:
                continue

            drafts.append(
                {
                    'text': text,
                    'options': [val for _, val in options] or ['', '', '', ''],
                    'correct': corr_int,
                }
            )

            if not text:
                errors.append(f'{display_num}-savol matnini kiriting.')
            elif len(nonempty) < 2:
                errors.append(f'{display_num}-savol uchun kamida 2 ta javob variantini kiriting.')
            elif correct not in {str(opt_i) for opt_i, _ in nonempty}:
                errors.append(f'{display_num}-savol uchun to‘g‘ri javobni belgilang.')
            else:
                prepared.append((text, nonempty, corr_int))

        # Fallback: direct raw text paste submission if cards were untouched
        raw_import = request.POST.get('raw_import_text', '').strip()
        if not drafts and raw_import:
            parsed_direct = parse_quiz_text(raw_import)
            for display_num, item in enumerate(parsed_direct, start=1):
                drafts.append(item)
                nonempty = [(opt_i, val) for opt_i, val in enumerate(item['options'], start=1) if val]
                if not item['correct']:
                    errors.append(f'{display_num}-savol uchun to‘g‘ri javob belgilanmagan.')
                else:
                    prepared.append((item['text'], nonempty, item['correct']))

        if not prepared and not errors:
            errors.append('Kamida bitta savol kiriting.')

        if not errors:
            with transaction.atomic():
                quiz = Quiz.objects.create(
                    title=title,
                    subject=subject,
                    description=description,
                    created_by=request.user,
                    is_published=_can_manage_content(request.user),
                )
                for order, (text, options, correct) in enumerate(prepared, start=1):
                    question = Question.objects.create(quiz=quiz, text=text, order=order)
                    for index, option_text in options:
                        AnswerOption.objects.create(
                            question=question, text=option_text, is_correct=(index == correct)
                        )
            messages.success(request, f'Test ({len(prepared)} ta savol) yaratildi va nashr qilindi.')
            return redirect('quiz_list')
        submitted_questions = drafts

    if not submitted_questions:
        submitted_questions = [
            {'text': '', 'options': ['', '', '', ''], 'correct': 0}
            for _ in range(3)
        ]

    return render(
        request,
        'catalog/create_quiz.html',
        {
            'errors': errors,
            'initial_questions_json': json.dumps(submitted_questions, ensure_ascii=False),
            'template_text': QUIZ_TEMPLATE_TEXT,
        },
    )


@login_required
def delete_quiz(request, pk):
    if not _can_manage_content(request.user):
        raise PermissionDenied
    if request.method == 'POST':
        quiz = get_object_or_404(Quiz, pk=pk)
        qtitle = quiz.title
        quiz.delete()
        messages.success(request, f"«{qtitle}» testi o‘chirildi.")
    return redirect(_admin_redirect_target(request, default_view='quiz_list'))


def quiz_list(request):
    subject_filter = request.GET.get('subject', '').strip()
    quizzes = Quiz.objects.filter(is_published=True).annotate(
        num_questions=Count('questions', distinct=True),
        num_attempts=Count('attempts', distinct=True),
    ).order_by('title')
    if subject_filter:
        quizzes = quizzes.filter(subject__iexact=subject_filter)
    subjects = (
        Quiz.objects.filter(is_published=True)
        .exclude(subject='')
        .values_list('subject', flat=True)
        .distinct()
        .order_by('subject')
    )
    return render(
        request,
        'catalog/quiz_list.html',
        {'quizzes': quizzes, 'subjects': subjects, 'selected_subject': subject_filter},
    )


@login_required
def take_quiz(request, pk):
    quiz = get_object_or_404(
        Quiz.objects.prefetch_related('questions__options'), pk=pk, is_published=True
    )
    questions = list(quiz.questions.all())
    if request.method == 'POST':
        score = 0
        for question in questions:
            answer_id = request.POST.get(f'q_{question.pk}')
            if answer_id and question.options.filter(pk=answer_id, is_correct=True).exists():
                score += 1
        attempt = QuizAttempt(
            user=request.user,
            quiz=quiz,
            score=score,
            total=len(questions),
        )
        if attempt.is_passed:
            attempt.certificate_code = (
                f'AL-{quiz.pk:02d}{request.user.pk:02d}-{secrets.token_hex(3).upper()}'
            )
            earned_points = score * 10 + 20
        else:
            earned_points = score * 5
        attempt.save()

        request.user.points = (request.user.points or 0) + earned_points
        request.user.save(update_fields=['points'])

        if attempt.is_passed:
            Notification.objects.create(
                user=request.user,
                title=f'Sertifikat taqdim etildi: {quiz.title}',
                message=f'Siz «{quiz.title}» testidan {attempt.percent}% natija ko‘rsatib, #{attempt.certificate_code} raqamli elektron sertifikat va +{earned_points} ball qo‘lga kiritdingiz!',
                url=reverse('certificate_view', args=[attempt.pk]),
            )

        messages.success(
            request,
            f'Test yakunlandi: {score}/{len(questions)} ({attempt.percent}%) · +{earned_points} ball qo‘shildi!',
        )
        return redirect('quiz_result', pk=attempt.pk)
    return render(request, 'catalog/take_quiz.html', {'quiz': quiz, 'questions': questions})


@login_required
def quiz_result(request, pk):
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related('quiz', 'user'), pk=pk, user=request.user
    )
    return render(request, 'catalog/quiz_result.html', {'attempt': attempt})


def certificate_view(request, pk):
    attempt = get_object_or_404(QuizAttempt.objects.select_related('quiz', 'user'), pk=pk)
    if not attempt.is_passed:
        messages.warning(
            request,
            'Ushbu natija bo‘yicha sertifikat mavjud emas (kamida 70% natija talab qilinadi).',
        )
        return redirect('quiz_list')
    if not attempt.certificate_code:
        attempt.certificate_code = (
            f'AL-{attempt.quiz.pk:02d}{attempt.user.pk:02d}-{secrets.token_hex(3).upper()}'
        )
        attempt.save(update_fields=['certificate_code'])
    return render(request, 'catalog/certificate.html', {'attempt': attempt})


def leaderboard(request):
    students = (
        User.objects.filter(role='student')
        .annotate(
            attempts_count=Count('quiz_attempts', distinct=True),
            books_read_count=Count('reading_progress', distinct=True),
        )
        .order_by('-points', '-id')[:25]
    )
    return render(request, 'catalog/leaderboard.html', {'students': list(students)})


def teachers_books(request):
    query = request.GET.get('q', '').strip()
    subject = request.GET.get('subject', '').strip()
    books = Book.objects.filter(approved=True, is_teacher_book=True).select_related('category')
    if subject:
        books = books.filter(subject__iexact=subject)
    if query:
        books = search_books(books, query)
    subjects = (
        Book.objects.filter(approved=True, is_teacher_book=True)
        .exclude(subject='')
        .values_list('subject', flat=True)
        .distinct()
        .order_by('subject')
    )
    favorites = (
        set(Favorite.objects.filter(user=request.user).values_list('book_id', flat=True))
        if request.user.is_authenticated
        else set()
    )
    return render(
        request,
        'catalog/teachers_books.html',
        {
            'books': books,
            'query': query,
            'subjects': subjects,
            'selected_subject': subject,
            'favorites': favorites,
        },
    )


@login_required
@require_POST
def mark_notification_read(request, pk):
    note = get_object_or_404(Notification, pk=pk, user=request.user)
    note.is_read = True
    note.save(update_fields=['is_read'])
    return redirect('dashboard')


@login_required
@require_POST
def ai_librarian(request):
    """Grounded catalogue helper; searches both local DB and curated Ziyouz PDF collection."""
    try:
        data = json.loads(request.body or '{}')
        question = str(data.get('question', '')).strip()[:500]
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'answer': 'Savolni qayta yuboring.', 'sources': []}, status=400)
    if len(question) < 3:
        return JsonResponse(
            {'answer': 'Iltimos, savolingizni biroz batafsilroq yozing.', 'sources': []}
        )

    matches = search_books(
        Book.objects.filter(approved=True), question, limit=5, ignore_words=STOPWORDS
    )
    if matches:
        sources = [
            {'title': b.title, 'author': b.author, 'url': reverse('book_detail', args=[b.pk])}
            for b in matches
        ]
        answer = (
            'Katalogdan savolingizga mos keluvchi manbalarni topdim. '
            'Kitob sahifasiga o‘tib, uni onlayn PDF ko‘rinishida mutolaa qilishingiz mumkin:\n\n'
            + '\n'.join(f'• {b.title} — {b.author} ({b.display_subject})' for b in matches)
        )
    else:
        sources = []
        answer = (
            'Hozirgi katalogdagi ma’lumotlardan aniq mos manba topilmadi. '
            'Boshqa kalit so‘z bilan qidiring yoki Bosh sahifadagi «Ziyouz & Global Qidiruv» '
            'bo‘limidan foydalaning.'
        )
    return JsonResponse({'answer': answer, 'sources': sources})


def service_worker(request):
    source = Path(__file__).resolve().parent / 'static' / 'catalog' / 'sw.js'
    response = HttpResponse(
        source.read_text(encoding='utf-8'), content_type='application/javascript; charset=utf-8'
    )
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response


def ziyouz_search_api(request):
    """Ziyouz.com / Ziyouz.uz / n.ziyouz.com API qidiruv endpointi (ichki tasdiqlangan PDF baza + jonli qidiruv)."""
    q = request.GET.get('q', '').strip()[:150]
    if len(q) < 2:
        default_results = [
            {
                'title': item['title'],
                'author': item['author'],
                'subject': item['subject'],
                'category': item['subject'],
                'url': item['pdf'],
                'pdf': item['pdf'],
                'type': 'PDF',
                'year': 'Ziyouz Fondi',
                'source': f"Ziyouz PDF · {item['subject']}",
            }
            for item in CURATED_ZIYOUZ_BOOKS[:8]
        ]
        return JsonResponse({'results': default_results})

    results = []
    seen_urls = set()

    # 0. Ichki tasdiqlangan Ziyouz to'g'ridan-to'g'ri PDF fondidan qidirish
    q_tokens = tokenize(q)
    if q_tokens:
        for item in CURATED_ZIYOUZ_BOOKS:
            item_tokens = tokenize(f"{item['title']} {item['author']} {item['subject']}")
            matched = sum(
                1 for qt in q_tokens if any(_token_score(qt, w) >= 0.72 for w in item_tokens)
            )
            if matched >= max(1, int(len(q_tokens) * 0.6)):
                seen_urls.add(item['pdf'])
                results.append({
                    'title': item['title'],
                    'author': item['author'],
                    'subject': item['subject'],
                    'category': item['subject'],
                    'url': item['pdf'],
                    'pdf': item['pdf'],
                    'type': 'PDF',
                    'year': 'Kutubxona fondi',
                    'source': item['subject'],
                })

        for item in _search_ziyouz_index(q, limit=40):
            if item['url'] in seen_urls:
                continue
            seen_urls.add(item['url'])
            open_url = reverse('ziyouz_open_book', args=[item['id']])
            results.append({
                'id': item['id'],
                'title': item['title'],
                'author': item['author'],
                'subject': item['subject'],
                'category': item['subject'],
                'url': f'{open_url}?mode=read',
                'pdf': f'{open_url}?mode=download',
                'cover_url': reverse('ziyouz_cover', args=[item['id']]),
                'type': 'PDF',
                'source': item['subject'],
            })

    headers = {'User-Agent': 'Mozilla/5.0 (UrganchLibrary/2.0)'}

    # 1. WordPress REST API (ziyouz.uz & ziyouz.com) if needed
    if len(results) < 8:
        for domain in ('https://ziyouz.uz', 'https://ziyouz.com'):
            api_url = f'{domain}/wp-json/wp/v2/posts?search={urllib.parse.quote(q)}&per_page=8'
            req = urllib.request.Request(api_url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=4) as resp:
                    items = json.loads(resp.read().decode('utf-8', errors='ignore'))
                    if isinstance(items, list):
                        for post in items:
                            raw_title = unescape(
                                _re.sub(
                                    r'<[^>]+>', '', (post.get('title') or {}).get('rendered', '')
                                ).strip()
                            )
                            if not raw_title:
                                continue
                            content_html = (post.get('content') or {}).get('rendered', '')
                            pdf_match = _re.search(r'''https?://[^\s"'<>]+\.pdf''', content_html, _re.I)
                            pdf_url = pdf_match.group(0) if pdf_match else ''
                            link = post.get('link') or domain
                            if (pdf_url or link) in seen_urls:
                                continue
                            seen_urls.add(pdf_url or link)
                            results.append({
                                'title': raw_title,
                                'author': 'Kutubxona manbasi',
                                'url': link,
                                'pdf': pdf_url,
                                'source': 'PDF fond',
                            })
            except Exception:
                pass

    return JsonResponse({'results': results[:24]})


# ---------------------------------------------------------------------------
# PDF proksi va PDF topuvchi (qidiruv natijasidagi kitobni sayt ichida PDF
# ko'rinishida o'qish uchun). Brauzer CORS cheklovlarini chetlab o'tadi.
# ---------------------------------------------------------------------------
_PDF_HOSTS = ('ziyouz.com', 'ziyouz.uz', 'archive.org', 'openlibrary.org')
_PDF_MAX_BYTES = 300 * 1024 * 1024
_PAGE_MAX_BYTES = 2 * 1024 * 1024
_UA = {'User-Agent': 'Mozilla/5.0 (UrganchLibrary/2.0)'}


def _allowed_hosts():
    extra = getattr(_settings, 'PDF_PROXY_EXTRA_HOSTS', ())
    return tuple(_PDF_HOSTS) + tuple(extra)


def _host_ok(url):
    """Faqat ishonchli domenlarga (va ularning subdomenlariga) ruxsat; ichki IP lar taqiqlangan."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        return False
    host = parts.hostname.lower()
    if not any(host == h or host.endswith('.' + h) for h in _allowed_hosts()):
        return False
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
            ):
                return False
    except Exception:
        return False
    return True


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urllib.parse.urlsplit(newurl)
        safe_path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/()'-.,_")
        clean_url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, safe_path, parts.query, parts.fragment))
        if not _host_ok(clean_url):
            raise urllib.error.URLError("Ruxsat etilmagan yo'naltirish")
        return super().redirect_request(req, fp, code, msg, headers, clean_url)


_opener = urllib.request.build_opener(_SafeRedirect)


@require_GET
def ziyouz_cover(request, dl_id):
    """Serve & cache genuine Page-1 title sheet cover for an indexed Ziyouz book."""
    _, by_id = _get_ziyouz_index()
    item = by_id.get(str(dl_id))
    if not item:
        raise Http404('Manba topilmadi.')

    covers_dir = Path(_settings.MEDIA_ROOT) / 'covers'
    covers_dir.mkdir(parents=True, exist_ok=True)
    safe_id = ''.join(c for c in str(dl_id) if c.isalnum())[:24] or 'item'
    cache_path = covers_dir / f'z_{safe_id}.jpg'

    if cache_path.exists() and cache_path.stat().st_size > 1000:
        resp = FileResponse(cache_path.open('rb'), content_type='image/jpeg')
        resp['Cache-Control'] = 'public, max-age=86400'
        return resp

    src_url = item['url']
    if not _host_ok(src_url):
        raise Http404('Ruxsat etilmagan manba.')
    try:
        with _opener.open(urllib.request.Request(src_url, headers=_UA), timeout=25) as upstream:
            ctype = (upstream.headers.get('Content-Type') or '').lower()
            raw = upstream.read(64 * 1024 * 1024)
        if 'pdf' not in ctype and not raw[:16].lstrip().startswith(b'%PDF'):
            raise Http404('PDF topilmadi.')
        jpg = render_pdf_cover_bytes(raw, max_width=520, quality=88)
        if not jpg:
            raise Http404('Muqova yaratilmadi.')
        cache_path.write_bytes(jpg)
        resp = HttpResponse(jpg, content_type='image/jpeg')
        resp['Cache-Control'] = 'public, max-age=86400'
        return resp
    except Http404:
        raise
    except Exception:
        raise Http404('Muqova yuklanmadi.')


@xframe_options_sameorigin
@require_GET
def ziyouz_open_book(request, dl_id):
    """Resolve an indexed Ziyouz book, register/link it in DB, and open reader/download/detail."""
    mode = request.GET.get('mode', 'detail')
    if mode == 'read' and not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={urllib.parse.quote(request.get_full_path())}")

    _, by_id = _get_ziyouz_index()
    item = by_id.get(str(dl_id))
    if not item:
        raise Http404('Kitob topilmadi.')

    src_url = item['url']
    if not _host_ok(src_url):
        raise Http404('Ruxsat etilmagan manba.')

    existing = Book.objects.filter(
        Q(title__iexact=item['title'], author__iexact=item['author']) | Q(external_url=src_url)
    ).first()
    if existing:
        book = existing
    else:
        resolved_url = src_url
        try:
            with _opener.open(urllib.request.Request(src_url, headers=_UA), timeout=12) as upstream:
                resolved_url = upstream.geturl()
        except Exception:
            resolved_url = src_url

        existing_resolved = Book.objects.filter(external_url=resolved_url).first()
        if existing_resolved:
            book = existing_resolved
        else:
            subj = (item.get('subject') or 'Badiiy adabiyot').strip()
            cat = Category.objects.filter(name__icontains=subj.split()[0]).first() or Category.objects.first()
            book = Book.objects.create(
                title=item['title'][:240],
                author=item['author'][:180],
                subject=subj[:100],
                category=cat,
                description=f"{item['author']} — «{item['title']}» ({subj}).",
                language='O‘zbek',
                external_url=resolved_url,
                approved=True,
                view_count=1,
            )
            safe_id = ''.join(c for c in str(dl_id) if c.isalnum())[:24] or 'item'
            cache_path = Path(_settings.MEDIA_ROOT) / 'covers' / f'z_{safe_id}.jpg'
            if cache_path.exists() and cache_path.stat().st_size > 1000:
                book.cover.save(f'title_{book.pk}.jpg', ContentFile(cache_path.read_bytes()), save=True)
            else:
                try:
                    with _opener.open(urllib.request.Request(resolved_url, headers=_UA), timeout=12) as u2:
                        raw = u2.read(14 * 1024 * 1024)
                    jpg = render_pdf_cover_bytes(raw, max_width=520, quality=88)
                    if jpg:
                        cache_path.parent.mkdir(parents=True, exist_ok=True)
                        cache_path.write_bytes(jpg)
                        book.cover.save(f'title_{book.pk}.jpg', ContentFile(jpg), save=True)
                except Exception:
                    pass

    if mode == 'read':
        return redirect('book_pdf', pk=book.pk)
    if mode == 'download':
        return redirect('download_book_file', pk=book.pk)
    return redirect('book_detail', pk=book.pk)


@require_GET
@xframe_options_sameorigin
def pdf_proxy(request):
    """/api/pdf/?url=...  — tashqi PDF ni (Range qo'llab-quvvatlanadi) o'zimiz orqali beradi."""
    url = request.GET.get('url', '').strip()
    if not _host_ok(url):
        return JsonResponse({'error': "Bu manbadan o'qishga ruxsat yo'q."}, status=400)
    headers = dict(_UA)
    if request.headers.get('Range'):
        headers['Range'] = request.headers['Range']
    try:
        upstream = _opener.open(urllib.request.Request(url, headers=headers), timeout=20)
    except urllib.error.HTTPError as e:
        return JsonResponse({'error': f'Manba {e.code} javob berdi.'}, status=502)
    except Exception:
        return JsonResponse({'error': "Manbaga ulanib bo'lmadi."}, status=502)

    ctype = (upstream.headers.get('Content-Type') or '').lower()
    first = upstream.read(1024)
    if 'pdf' not in ctype and not first.lstrip().startswith(b'%PDF'):
        upstream.close()
        return JsonResponse({'error': 'Bu havola PDF fayl emas.'}, status=415)
    length = upstream.headers.get('Content-Length')
    if length and length.isdigit() and int(length) > _PDF_MAX_BYTES:
        upstream.close()
        return JsonResponse({'error': 'Fayl juda katta.'}, status=413)

    def stream():
        sent = len(first)
        yield first
        try:
            while sent < _PDF_MAX_BYTES:
                chunk = upstream.read(64 * 1024)
                if not chunk:
                    break
                sent += len(chunk)
                yield chunk
        finally:
            upstream.close()

    resp = StreamingHttpResponse(
        stream(),
        status=upstream.status if upstream.status in (200, 206) else 200,
        content_type='application/pdf',
    )
    for h in ('Content-Length', 'Content-Range', 'Accept-Ranges'):
        if upstream.headers.get(h):
            resp[h] = upstream.headers[h]
    if request.GET.get('download') == '1':
        fname = request.GET.get('filename') or url.split('/')[-1].split('?')[0] or 'kitob.pdf'
        resp['Content-Disposition'] = f'attachment; filename="{urllib.parse.quote(fname)}"'
    else:
        resp['Content-Disposition'] = 'inline'
    resp['Cache-Control'] = 'public, max-age=3600'
    return resp


@require_GET
def pdf_resolve(request):
    """/api/pdf-topish/?url=<kitob sahifasi>  — sahifadan PDF havolasini topadi."""
    page = request.GET.get('url', '').strip()
    if not _host_ok(page):
        return JsonResponse({'pdf': ''})
    try:
        with _opener.open(urllib.request.Request(page, headers=_UA), timeout=12) as resp:
            if 'pdf' in (resp.headers.get('Content-Type') or '').lower():
                return JsonResponse({'pdf': resp.geturl()})
            html_text = resp.read(_PAGE_MAX_BYTES).decode('utf-8', errors='ignore')
            base = resp.geturl()
    except Exception:
        return JsonResponse({'pdf': ''})
    found = []
    for href in _re.findall(
        r'(?:href|src|data-src|data-url)\s*=\s*["\']([^"\']+?\.pdf(?:\?[^"\']*)?)["\']',
        html_text,
        _re.I,
    ):
        full = urllib.parse.urljoin(base, href.replace('&amp;', '&'))
        if full not in found and _host_ok(full):
            found.append(full)
    if not found:
        for full in _re.findall(r'https?://[^\s"\'<>]+?\.pdf', html_text, _re.I):
            if full not in found and _host_ok(full):
                found.append(full)
    return JsonResponse({'pdf': found[0] if found else '', 'all': found[:5]})


@require_http_methods(['GET', 'HEAD'])
def health_check(request):
    """Render va UptimeRobot uchun tezkor tiriklik tekshiruvi (/healthz/)."""
    return HttpResponse('ok', content_type='text/plain')
