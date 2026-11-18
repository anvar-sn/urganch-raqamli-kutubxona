import json
from django.test import TestCase
from django.urls import reverse
from .models import User, Book, Category, Quiz, Question, AnswerOption, ReadingProgress, QuizAttempt


class LibraryTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username='student1',
            password='StrongPass123!',
            role='student',
            first_name='Sardor',
            last_name='Karimov',
            group_name='101-Aniq fanlar',
        )
        self.book = Book.objects.create(
            title='Python asoslari',
            author='Ali Valiyev',
            subject='Informatika',
            description='Dasturlash kitobi',
            external_url='https://n.ziyouz.com/books/kollej_va_otm_darsliklari/informatika/Informatika%20va%20axborot%20texnologiyalari%20(A.Sattorov).pdf',
            is_teacher_book=True,
            approved=True,
        )

    def test_home_shows_approved_books_and_searches(self):
        response = self.client.get(reverse('home'), {'q': 'Python'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Python asoslari')
        self.assertEqual(
            self.client.get(reverse('home'), {'q': 'bo‘lmagan kitob'}).context['page_obj'].paginator.count,
            0,
        )

    def test_unapproved_book_is_not_public(self):
        pending = Book.objects.create(title='Tekshiruvda', author='Muallif', approved=False)
        self.assertEqual(self.client.get(reverse('book_detail', args=[pending.pk])).status_code, 404)

    def test_pdf_reader_requires_login(self):
        self.assertEqual(self.client.get(reverse('book_pdf', args=[self.book.pk])).status_code, 302)

    def test_student_cannot_upload_book(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('upload_book')).status_code, 403)

    def test_progress_endpoint_saves_user_progress_and_awards_points(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse('save_progress', args=[self.book.pk]),
            data=json.dumps({'page': 5, 'total': 20}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        progress = ReadingProgress.objects.get(user=self.student, book=self.book)
        self.assertEqual(progress.current_page, 5)
        self.assertEqual(progress.percent, 25)
        self.student.refresh_from_db()
        self.assertGreaterEqual(self.student.points, 10)

    def test_ai_helper_returns_catalog_sources(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse('ai_librarian'),
            data=json.dumps({'question': 'Python asoslari'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['sources'][0]['title'], 'Python asoslari')

    def test_quiz_is_graded_server_side_and_generates_certificate(self):
        self.client.force_login(self.student)
        quiz = Quiz.objects.create(title='Python testi', is_published=True)
        question = Question.objects.create(quiz=quiz, text='Python nima?')
        right = AnswerOption.objects.create(question=question, text='Dasturlash tili', is_correct=True)
        AnswerOption.objects.create(question=question, text='Brauzer')
        response = self.client.post(reverse('take_quiz', args=[quiz.pk]), {f'q_{question.pk}': str(right.pk)})
        self.assertEqual(response.status_code, 302)
        attempt = QuizAttempt.objects.get(user=self.student, quiz=quiz)
        self.assertEqual(attempt.score, 1)
        self.assertTrue(attempt.is_passed)
        self.assertTrue(len(attempt.certificate_code) >= 8)

        cert_res = self.client.get(reverse('certificate_view', args=[attempt.pk]))
        self.assertEqual(cert_res.status_code, 200)
        self.assertContains(cert_res, attempt.certificate_code)

        cert_qr = self.client.get(reverse('certificate_qrcode', args=[attempt.pk]))
        self.assertEqual(cert_qr.status_code, 200)
        self.assertEqual(cert_qr['Content-Type'], 'image/png')

    def test_teachers_books_and_leaderboard_and_qr(self):
        res_teachers = self.client.get(reverse('teachers_books'))
        self.assertEqual(res_teachers.status_code, 200)
        self.assertContains(res_teachers, 'Python asoslari')

        res_leader = self.client.get(reverse('leaderboard'))
        self.assertEqual(res_leader.status_code, 200)
        self.assertContains(res_leader, 'Sardor Karimov')

        res_qr = self.client.get(reverse('book_qrcode', args=[self.book.pk]))
        self.assertEqual(res_qr.status_code, 200)
        self.assertEqual(res_qr['Content-Type'], 'image/png')

    def test_download_book_increments_counter(self):
        res = self.client.get(reverse('download_book_file', args=[self.book.pk]))
        self.assertEqual(res.status_code, 302)
        self.book.refresh_from_db()
        self.assertEqual(self.book.download_count, 1)

    def test_ziyouz_search_api_and_legacy_hub(self):
        res_api = self.client.get(reverse('ziyouz_search_api'), {'q': 'Navoiy'})
        self.assertEqual(res_api.status_code, 200)
        data = res_api.json()
        self.assertTrue(len(data['results']) >= 1)

        res_hub = self.client.get(reverse('legacy_index'))
        self.assertEqual(res_hub.status_code, 200)

    def test_uzedu_sign_in_and_dashboard_routes(self):
        res_signin = self.client.get('/sign-in?redirectURL=%2Fdashboard')
        self.assertEqual(res_signin.status_code, 200)
        self.assertContains(res_signin, 'UrDU AKADEMIK LITSEYI')

        res_dash = self.client.get('/dashboard')
        self.assertEqual(res_dash.status_code, 200)
        self.assertContains(res_dash, 'Xorazm viloyati')
        self.assertContains(res_dash, 'uzedu-uz-svg')

        res_oneid = self.client.post('/sign-in/', {'oneid_login': '1', 'oneid_role': 'student1', 'redirectURL': '/dashboard'})
        self.assertEqual(res_oneid.status_code, 302)
        self.assertEqual(res_oneid['Location'], '/dashboard')

    def test_workspaces_and_admin_user_crud(self):
        admin_user = User.objects.create_user(
            username='admin_boss',
            password='Password123!',
            role='librarian',
            is_staff=True,
            first_name='Kutubxona',
            last_name='Mudiri',
        )

        # 1. Test Workspaces rendering
        self.client.force_login(admin_user)
        res_admin_ws = self.client.get(reverse('dashboard') + '?workspace=admin')
        self.assertEqual(res_admin_ws.status_code, 200)
        self.assertContains(res_admin_ws, 'Foydalanuvchilar boshqaruvi')
        self.assertContains(res_admin_ws, 'Kitoblar fondi')

        res_teacher_ws = self.client.get(reverse('dashboard') + '?workspace=teacher')
        self.assertEqual(res_teacher_ws.status_code, 200)
        self.assertContains(res_teacher_ws, 'Kutubxonachi Ishchi Stoli')

        res_student_ws = self.client.get(reverse('dashboard') + '?workspace=student')
        self.assertEqual(res_student_ws.status_code, 200)
        self.assertContains(res_student_ws, 'O‘quvchi Shaxsiy Ishchi Stoli')

        # 2. Admin adds a new user
        add_res = self.client.post(reverse('admin_add_user'), {
            'username': 'yangi_oquvchi_2026',
            'password': 'Pass2026Secure!',
            'first_name': 'Jasurbek',
            'last_name': 'Otaboyev',
            'role': 'student',
            'group_name': '102-Aniq fanlar',
            'email': 'jasur@urdu.uz',
        })
        self.assertEqual(add_res.status_code, 302)
        created_user = User.objects.get(username='yangi_oquvchi_2026')
        self.assertEqual(created_user.first_name, 'Jasurbek')
        self.assertEqual(created_user.role, 'student')
        self.assertEqual(created_user.group_name, '102-Aniq fanlar')

        # 3. Admin changes user role
        role_res = self.client.post(reverse('admin_change_user_role', args=[created_user.pk]), {'role': 'teacher'})
        self.assertEqual(role_res.status_code, 302)
        created_user.refresh_from_db()
        self.assertEqual(created_user.role, 'teacher')

        # 4. Admin deletes user
        del_res = self.client.post(reverse('admin_delete_user', args=[created_user.pk]))
        self.assertEqual(del_res.status_code, 302)
        self.assertFalse(User.objects.filter(username='yangi_oquvchi_2026').exists())

        # 5. Admin cannot delete self
        self_del_res = self.client.post(reverse('admin_delete_user', args=[admin_user.pk]))
        self.assertEqual(self_del_res.status_code, 302)
        self.assertTrue(User.objects.filter(username='admin_boss').exists())

        # 6. Non-admin student cannot add, delete, or change role of users
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(reverse('admin_add_user'), {'username': 'hacker'}).status_code, 403)
        self.assertEqual(self.client.post(reverse('admin_delete_user', args=[admin_user.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('admin_change_user_role', args=[admin_user.pk]), {'role': 'student'}).status_code, 403)

    def test_teacher_books_navbar_visibility_and_admin_toggle(self):
        admin_user = User.objects.create_user(
            username='admin_nav',
            password='Password123!',
            role='librarian',
            is_staff=True,
        )
        self.client.force_login(self.student)
        res_with = self.client.get(reverse('home'))
        self.assertContains(res_with, 'Ustozlar kitoblari')

        # Admin toggles teacher flag off -> navbar hides "Ustozlar kitoblari"
        self.client.force_login(admin_user)
        toggle_res = self.client.post(
            reverse('admin_toggle_teacher_book', args=[self.book.pk]),
            {'next': reverse('profile') + '?workspace=admin'},
        )
        self.assertEqual(toggle_res.status_code, 302)
        self.book.refresh_from_db()
        self.assertFalse(self.book.is_teacher_book)

        res_without = self.client.get(reverse('home'))
        self.assertNotContains(res_without, 'Ustozlar kitoblari')

        # Toggle back on -> navbar shows again
        self.client.post(reverse('admin_toggle_teacher_book', args=[self.book.pk]))
        res_restored = self.client.get(reverse('home'))
        self.assertContains(res_restored, 'Ustozlar kitoblari')

    def test_dynamic_unlimited_quiz_creation_and_import(self):
        teacher = User.objects.create_user(
            username='ustoz1',
            password='Password123!',
            role='teacher',
        )
        self.client.force_login(teacher)

        # 1. Template download & Google Docs text import API
        tpl_res = self.client.get(reverse('parse_quiz_import_api'), {'template': '1'})
        self.assertEqual(tpl_res.status_code, 200)
        self.assertIn('Mahbub ul-qulub', tpl_res.content.decode('utf-8'))

        raw_doc = "\n\n".join(
            f"{i}. Savol matni {i}?\n*A) To'g'ri {i}\nB) Xato {i}b\nC) Xato {i}c\nD) Xato {i}d"
            for i in range(1, 9)
        )
        imp_res = self.client.post(reverse('parse_quiz_import_api'), {'raw_text': raw_doc})
        self.assertEqual(imp_res.status_code, 200)
        self.assertEqual(imp_res.json()['count'], 8)

        # 2. Submit all 8 dynamic questions (exceeding old limit of 5)
        post_data = {'title': 'Kattta dinamik test', 'subject': 'Matematika', 'description': '8 ta savol'}
        for i in range(1, 9):
            post_data[f'question_{i}'] = f'Savol {i}'
            post_data[f'option_{i}_1'] = f'Javob A {i}'
            post_data[f'option_{i}_2'] = f'Javob B {i}'
            post_data[f'option_{i}_3'] = f'Javob C {i}'
            post_data[f'correct_{i}'] = '2'

        save_res = self.client.post(reverse('create_quiz'), post_data)
        self.assertEqual(save_res.status_code, 302)
        created = Quiz.objects.get(title='Kattta dinamik test')
        self.assertEqual(created.questions.count(), 8)
        self.assertTrue(created.is_published)

        # 3. Kutubxonachi can also upload approved catalog books & delete quizzes
        up_res = self.client.post(reverse('upload_book'), {
            'title': 'Kutubxonachi qo‘shgan kitob',
            'author': 'Muallif Test',
            'subject': 'Fizika',
            'language': 'O‘zbek',
        })
        self.assertEqual(up_res.status_code, 302)
        self.assertTrue(Book.objects.filter(title='Kutubxonachi qo‘shgan kitob', approved=True).exists())

        del_q_res = self.client.post(reverse('delete_quiz', args=[created.pk]))
        self.assertEqual(del_q_res.status_code, 302)
        self.assertFalse(Quiz.objects.filter(pk=created.pk).exists())

    def test_ziyouz_full_index_search_returns_many_matches(self):
        self.client.force_login(self.student)
        res = self.client.get(reverse('home'), {'q': 'Navoiy'})
        self.assertEqual(res.status_code, 200)
        remote = res.context['remote_books']
        self.assertGreater(len(remote), 15)

    def test_profile_admin_edit_user_and_clean_layout(self):
        admin_user = User.objects.create_user(
            username='boss_admin',
            password='Password123!',
            role='librarian',
            is_staff=True,
        )
        self.client.force_login(admin_user)

        # Clean profile page has no redundant 3-role switcher tabs and exposes edit modal
        prof_res = self.client.get(reverse('profile'))
        self.assertEqual(prof_res.status_code, 200)
        self.assertContains(prof_res, 'openEditUserModal')
        self.assertNotContains(prof_res, 'Admin boshqaruvi')

        # Edit student details, role, and password
        edit_res = self.client.post(
            reverse('admin_edit_user', args=[self.student.pk]),
            {
                'username': 'sardor_edited',
                'first_name': 'Sardorbek',
                'last_name': 'Karimov',
                'group_name': '205-Aniq',
                'phone': '+998901112233',
                'role': 'teacher',
                'password': 'NewPass456!',
                'next': reverse('profile'),
            },
        )
        self.assertEqual(edit_res.status_code, 302)
        self.assertEqual(edit_res['Location'], reverse('profile'))
        self.student.refresh_from_db()
        self.assertEqual(self.student.username, 'sardor_edited')
        self.assertEqual(self.student.first_name, 'Sardorbek')
        self.assertEqual(self.student.phone, '+998901112233')
        self.assertEqual(self.student.role, 'teacher')
        self.assertTrue(self.student.check_password('NewPass456!'))

        # Toggle active status for other user vs self guard
        tog_res = self.client.post(
            reverse('admin_toggle_user_active', args=[self.student.pk]),
            {'next': reverse('profile')},
        )
        self.assertEqual(tog_res.status_code, 302)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)

        self.client.post(reverse('admin_toggle_user_active', args=[admin_user.pk]))
        admin_user.refresh_from_db()
        self.assertTrue(admin_user.is_active)

    def test_health_check_and_seed_command(self):
        import io
        from django.core.management import call_command
        from django.test import override_settings

        get_res = self.client.get(reverse('health_check'))
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.content, b'ok')

        head_res = self.client.head(reverse('health_check'))
        self.assertEqual(head_res.status_code, 200)

        with override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r'^healthz/$']):
            exempt_res = self.client.get(reverse('health_check'))
            self.assertEqual(exempt_res.status_code, 200)

        out = io.StringIO()
        call_command('ensure_library_seed', stdout=out)
        self.assertIn('skipping seed', out.getvalue().lower())
