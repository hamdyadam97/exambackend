#!/usr/bin/env python
"""
Seed script for RootsExams platform.

Usage:
    python scripts/seed_platform.py
    python scripts/seed_platform.py --clear

Creates realistic demo data: users, categories, questions, exams,
packages, subscriptions, payments, notifications, testimonials, etc.
"""
import argparse
import os
import random
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import django

django.setup()

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.users.models import User, UserProfile
from apps.content.models import (
    Category, QuestionsTopic, ExamSection, Blog, BlogComment, Testimonial,
    Notification, NotificationReceipt, AppInfo, Partner, ContactMessage,
    SupportRequest, Instructor, Faq, AiInstruction, Setting,
)
from apps.exams.models import (
    Question, Answer, QuestionTopic, ExamSectionLink,
    Exam, ExamQuestion, UserExam, UserExamAnswer,
)
from apps.packages.models import (
    Package, UserPackage, DiscountCode,
)
from apps.payments.models import (
    PaymentType, PaymentTransaction, MoneyLog, Invoice,
)

random.seed(42)

STUDENT_PASSWORD = 'student123'


def _user(role, phone, password, **kwargs):
    defaults = {
        'first_name': kwargs.get('first_name', 'User'),
        'last_name': kwargs.get('last_name', str(phone)[-4:]),
        'role_type': role,
        'status': User.ACTIVE,
        'is_phone_verified': True,
    }
    if role == User.ROLE_ADMIN:
        defaults['is_staff'] = True
        defaults['is_superuser'] = True
    elif role in (User.ROLE_ACCOUNTANT, User.ROLE_DATA_ENTRY):
        defaults['is_staff'] = True
    defaults.update(kwargs)
    user, created = User.objects.update_or_create(phone=phone, defaults=defaults)
    user.set_password(password)
    user.save(update_fields=['password'])
    return user


def clear_existing_data():
    print('Clearing existing demo data...')
    # Order matters for FK constraints
    UserExamAnswer.objects.all().delete()
    UserExam.objects.all().delete()
    ExamQuestion.objects.all().delete()
    Exam.objects.all().delete()
    ExamSectionLink.objects.all().delete()
    QuestionTopic.objects.all().delete()
    Answer.objects.all().delete()
    Question.objects.all().delete()
    SupportRequest.objects.all().delete()
    AiInstruction.objects.all().delete()
    Testimonial.objects.all().delete()
    BlogComment.objects.all().delete()
    Blog.objects.all().delete()
    NotificationReceipt.objects.all().delete()
    Notification.objects.all().delete()
    ContactMessage.objects.all().delete()
    Invoice.objects.all().delete()
    PaymentTransaction.objects.all().delete()
    MoneyLog.objects.all().delete()
    UserPackage.objects.all().delete()
    Package.objects.all().delete()
    DiscountCode.objects.all().delete()
    Partner.objects.all().delete()
    Faq.objects.all().delete()
    Instructor.objects.all().delete()
    ExamSection.objects.all().delete()
    QuestionsTopic.objects.all().delete()
    AppInfo.objects.all().delete()
    Setting.objects.all().delete()
    Category.objects.all().delete()
    print('Existing data cleared.')


def create_users():
    print('Creating users...')
    admin = _user(
        User.ROLE_ADMIN, '+962790000001', 'admin123',
        first_name='مدير', last_name='النظام', email='admin@rootsexams.com'
    )
    accountant = _user(
        User.ROLE_ACCOUNTANT, '+962790000003', 'accountant123',
        first_name='محاسب', last_name='رقمي', email='accountant@rootsexams.com'
    )
    dataentry = _user(
        User.ROLE_DATA_ENTRY, '+962790000004', 'dataentry123',
        first_name='مدخل', last_name='بيانات', email='dataentry@rootsexams.com'
    )

    students = []
    first_names = ['أحمد', 'محمد', 'خالد', 'يوسف', 'عمر', 'علي', 'سارة', 'لينا', 'ريما', 'هند']
    last_names = ['الأحمد', 'الخالدي', 'العمري', 'الحسن', 'السعدي', 'الريان', 'الناصر', 'العبيدي', 'السالم', 'الحجازي']
    for i in range(10):
        phone = f'+96279{1000100 + i}'
        user = _user(
            User.ROLE_USER, phone, STUDENT_PASSWORD,
            first_name=random.choice(first_names),
            last_name=random.choice(last_names),
            email=f'student{i+1}@rootsexams.com',
        )
        UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'specialization': random.choice(['طب', 'هندسة', 'صيدلة', 'تمريض']),
                'governorate': random.choice(['عمان', 'إربد', 'الزرقاء', 'المفرق']),
                'birth_date': date(1995, 1, 1) + timedelta(days=random.randint(0, 3000)),
                'profile_completed': True,
            }
        )
        students.append(user)

    return {
        'admin': admin,
        'accountant': accountant,
        'dataentry': dataentry,
        'students': students,
    }


def create_categories():
    print('Creating categories...')
    tree = {
        'الطب البشري': {
            'الطب الباطني': ['القلب والأوعية الدموية', 'الجهاز الهضمي', 'الغدد الصماء'],
            'الجراحة': ['جراحة العظام', 'جراحة الأعصاب', 'جراحة البطن'],
        },
        'التمريض': {
            'التمريض العام': ['تمريض البالغين', 'تمريض الأطفال'],
            'التمريض المتخصص': ['العناية المركزة', 'تمريض الطوارئ'],
        },
        'الصيدلة': {
            'الصيدلة الإكلينيكية': ['الأدوية الجهازية', 'التفاعلات الدوائية'],
            'الصيدلة الصناعية': ['تصنيع الأدوية', 'الجودة الدوائية'],
        },
    }

    main_cats = []
    sub_cats = []
    sub_sub_cats = []

    category_meta = {
        'الطب البشري': {
            'description': 'تخصص شامل يغطي تشخيص وعلاج الأمراض الباطنية والجراحية مع امتحانات تدريبية متخصصة.',
            'icon': 'stethoscope',
            'is_top': True,
            'is_new': False,
        },
        'التمريض': {
            'description': 'دورات وامتحانات للتمريض العام والمتخصص بما في ذلك العناية المركزة وتمريض الطوارئ.',
            'icon': 'heart-pulse',
            'is_top': True,
            'is_new': False,
        },
        'الصيدلة': {
            'description': 'تدريب متخصص في الصيدلة الإكلينيكية والصناعية، الأدوية الجهازية، والجودة الدوائية.',
            'icon': 'pill',
            'is_top': False,
            'is_new': True,
        },
    }

    for main_name, subs in tree.items():
        meta = category_meta.get(main_name, {})
        main = Category.objects.create(
            name=main_name, level=Category.LEVEL_CATEGORY,
            description=meta.get('description'),
            icon=meta.get('icon'),
            order=random.randint(1, 5), status=Category.ACTIVE,
            foreground_color='#ffffff', background_color='#4f46e5',
            is_top=meta.get('is_top', False),
            is_new=meta.get('is_new', False),
        )
        main_cats.append(main)
        for sub_name, sub_sub_names in subs.items():
            sub = Category.objects.create(
                name=sub_name, level=Category.LEVEL_SUB_CATEGORY,
                parent=main, order=random.randint(1, 5), status=Category.ACTIVE,
            )
            sub_cats.append(sub)
            for ss_name in sub_sub_names:
                ss = Category.objects.create(
                    name=ss_name, level=Category.LEVEL_SUB_SUB_CATEGORY,
                    parent=sub, order=random.randint(1, 5), status=Category.ACTIVE,
                )
                sub_sub_cats.append(ss)

    return main_cats, sub_cats, sub_sub_cats


def create_topics_and_sections(main_cats, sub_cats):
    print('Creating topics and exam sections...')
    topics = []
    sections = []
    topic_names = [
        'التشريح', 'الفيزيولوجيا', 'الكيمياء الحيوية', 'الأدوية',
        'التمريض السريري', 'الصيدلة الإكلينيكية', 'الأحياء الدقيقة',
    ]
    section_names = [
        'قسم أساسي', 'قسم متقدم', 'قسم المراجعة', 'قسم الامتحان التجريبي',
    ]
    for cat in main_cats:
        for _ in range(2):
            topics.append(QuestionsTopic.objects.create(
                topic=f'{random.choice(topic_names)} - {cat.name}',
                category=cat,
            ))
            sections.append(ExamSection.objects.create(
                name=f'{random.choice(section_names)} - {cat.name}',
                category=cat,
            ))
    for cat in sub_cats:
        if random.random() > 0.5:
            topics.append(QuestionsTopic.objects.create(
                topic=f'{random.choice(topic_names)} - {cat.name}',
                category=cat,
            ))
    return topics, sections


def create_questions(main_cats, sub_cats, sub_sub_cats, topics, sections, count=60):
    print(f'Creating {count} questions with answers...')
    questions = []
    for i in range(count):
        answer_type = random.choice([Question.ANSWER_TYPE_RADIO, Question.ANSWER_TYPE_MULTIPLE])
        cat = random.choice(main_cats)
        sub = random.choice([c for c in sub_cats if c.parent == cat] or sub_cats)
        sub_sub = random.choice([c for c in sub_sub_cats if c.parent == sub] or sub_sub_cats)

        q = Question.objects.create(
            text_question=f'سؤال رقم {i+1} في {cat.name} / {sub.name}؟',
            notes='ملاحظات توضيحية للسؤال.',
            status=Question.ACTIVE,
            question_type=Question.QUESTION_TYPE_QUESTION,
            answer_type=answer_type,
            hint='تلميح: اقرأ السؤال جيداً.',
            show_answer_explanation=True,
            show_hint=True,
            show_answer=True,
            time_minutes=random.choice([1, 2, 3]),
            category=cat,
            sub_category=sub,
            sub_subcategory=sub_sub,
            sort_order=i,
        )
        answers = []
        for letter in ['أ', 'ب', 'ت', 'ث']:
            answers.append(Answer.objects.create(
                question=q,
                answer_option=f'إجابة {letter}',
            ))
        correct = random.choice(answers)
        q.correct_answer = correct
        q.save(update_fields=['correct_answer'])

        if topics:
            QuestionTopic.objects.get_or_create(
                question=q,
                topic=random.choice(topics),
            )
        if sections and random.random() > 0.5:
            ExamSectionLink.objects.get_or_create(
                question=q,
                section=random.choice(sections),
            )
        questions.append(q)
    return questions


def create_exams(main_cats, sub_cats, questions):
    print('Creating exams...')
    exams = []
    exam_titles = [
        'امتحان تدريبي 1', 'امتحان تدريبي 2', 'امتحان نهائي',
        'اختبار تحديد المستوى', 'مراجعة شاملة',
    ]
    for i, title in enumerate(exam_titles):
        cat = random.choice(main_cats)
        sub = random.choice([c for c in sub_cats if c.parent == cat] or sub_cats)
        exam = Exam.objects.create(
            title=f'{title} - {cat.name}',
            description='وصف الامتحان والمحتوى المغطى.',
            duration_minutes=random.choice([30, 45, 60]),
            status=Exam.ACTIVE,
            category=cat,
            sub_category=sub,
            order=i,
            score=100,
        )
        picked = random.sample(questions, min(random.randint(5, 12), len(questions)))
        for idx, q in enumerate(picked):
            ExamQuestion.objects.create(exam=exam, question=q, order=idx)
        exams.append(exam)
    return exams


def create_packages(main_cats, exams, instructors):
    print('Creating packages...')
    packages = []
    course_images = [
        'https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=800&q=80',
        'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=800&q=80',
        'https://images.unsplash.com/photo-1503676260728-1c00da094a0b?auto=format&fit=crop&w=800&q=80',
        'https://images.unsplash.com/photo-1579684385127-1ef15d508118?auto=format&fit=crop&w=800&q=80',
        'https://images.unsplash.com/photo-1557804506-669a67965ba0?auto=format&fit=crop&w=800&q=80',
        'https://images.unsplash.com/photo-1556761175-5973dc0f32e7?auto=format&fit=crop&w=800&q=80',
    ]
    course_names = [
        'باقة التمريض الشاملة',
        'باقة الطب البشري المتكاملة',
        'باقة الصيدلة الإكلينيكية',
        'باقة الهندسة المدنية',
        'باقة الجمال والجلدية',
        'باقة التقنية والبرمجة',
    ]
    languages = ['العربية', 'English', 'العربية', 'English', 'العربية', 'English']
    for i, name in enumerate(course_names):
        cat = random.choice(main_cats)
        price = Decimal(random.choice(['15.00', '25.00', '35.00', '45.00']))
        discount = random.choice([0, 0, 10, 20])
        pkg = Package.objects.create(
            name=name,
            code=f'CRS-{i+1:03d}',
            description='دورة احترافية تشمل محاضرات مسجلة، أسئلة تدريبية، امتحانات تجريبية، ومتابعة مستمرة لضمان النجاح.',
            logo=course_images[i % len(course_images)],
            price=price,
            status=Package.ACTIVE,
            period_days=random.choice([30, 60, 90]),
            duration_minutes=random.choice([120, 240, 360, 480]),
            number_of_questions=random.choice([100, 200, 500]),
            category=cat,
            instructor=random.choice(instructors) if instructors else None,
            language=languages[i % len(languages)],
            lessons_count=random.randint(10, 40),
            is_trial=False,
            is_bestseller=(i == 0),
            is_new=(i == 1),
            is_featured=(i < 3),
            difficulty_level=random.choice([Package.BEGINNER, Package.INTERMEDIATE, Package.ADVANCED]),
            rating=Decimal(str(round(random.uniform(3.8, 5.0), 1))),
            students_count=random.randint(200, 8000),
            discount_percentage=discount,
        )
        packages.append(pkg)

    # Trial package
    trial_cat = random.choice(main_cats)
    trial = Package.objects.create(
        name='باقة تجريبية مجانية',
        code='TRIAL-001',
        description='جرب المنصة مجاناً مع عدد محدود من الأسئلة وامتحان قصير.',
        logo='https://images.unsplash.com/photo-1434030216411-0b793f4b4173?auto=format&fit=crop&w=800&q=80',
        price=Decimal('0.00'),
        status=Package.ACTIVE,
        period_days=7,
        duration_minutes=60,
        number_of_questions=50,
        category=trial_cat,
        instructor=random.choice(instructors) if instructors else None,
        language='العربية',
        lessons_count=5,
        is_trial=True,
        is_new=True,
        difficulty_level=Package.BEGINNER,
        rating=Decimal('4.5'),
        students_count=random.randint(500, 2000),
    )
    packages.append(trial)

    # Custom package: user selects days
    custom = Package.objects.create(
        name='باقة مخصصة',
        code='CUSTOM',
        description='باقة مرنة تختار فيها عدد الأيام اللي بدّك إياها، وبتدفع حسب اليوم.',
        logo='https://placehold.co/128x128/7c3aed/ffffff?text=Custom',
        price=Decimal('0.00'),
        status=Package.ACTIVE,
        daily_rate=Decimal('1.00'),
        number_of_questions=1000,
        category=random.choice(main_cats),
        instructor=random.choice(instructors) if instructors else None,
        language='العربية',
        lessons_count=20,
        is_custom=True,
    )
    packages.append(custom)

    return packages


def create_subscriptions_payments_invoices(users, packages, payment_types):
    print('Creating subscriptions, payments and invoices...')
    admin = users['admin']
    for student in users['students']:
        fixed_packages = [p for p in packages if not p.is_custom]
        for pkg in random.sample(fixed_packages, random.randint(1, 2)):
            start = timezone.now().date() - timedelta(days=random.randint(0, 20))
            end = start + timedelta(days=pkg.period_days or 30)
            sub = UserPackage.objects.create(
                user=student,
                package=pkg,
                start_date=start,
                end_date=end,
                price=pkg.price,
                subscription_status=UserPackage.ACTIVE,
            )
            invoice = Invoice.objects.create(
                user=student,
                user_package=sub,
                invoice_number=f'INV-{student.id}-{pkg.id}-{random.randint(1000,9999)}',
                total_amount=pkg.price,
                status=Invoice.STATUS_PAID,
                created_by=admin,
                sent_by=admin,
                sent_at=timezone.now(),
            )
            PaymentTransaction.objects.create(
                user=student,
                package=pkg,
                transaction_type='purchase',
                payment_id=f'PAY-{random.randint(100000,999999)}',
                amount=pkg.price,
                currency='JOD',
                is_success=True,
            )
            MoneyLog.objects.create(
                user=student,
                item=pkg,
                platform=random.choice(['web', 'mobile', 'ios', 'android']),
                payment_id=f'PAY-{random.randint(100000,999999)}',
                status=1,
            )


def create_notifications(users):
    print('Creating notifications...')
    titles = [
        'تم إضافة امتحان جديد',
        'تذكير بالاشتراك',
        'تحديثات المنصة',
    ]
    for title in titles:
        note = Notification.objects.create(
            title=title,
            description=f'{title} - تفاصيل إضافية للمستخدم.',
        )
        for student in users['students']:
            NotificationReceipt.objects.get_or_create(
                notification=note,
                user=student,
                defaults={'is_read': random.random() > 0.5},
            )


def create_testimonials(users):
    print('Creating testimonials...')
    texts = [
        'منصة ممتازة وسهلة الاستخدام.',
        'ساعدتني كثيراً في الاستعداد للامتحان.',
        'أسئلة متنوعة وشرح واضح.',
        'أنصح الجميع بالاشتراك.',
        'تجربة رائعة ونتائج مميزة.',
    ]
    specialties = ['الطب البشري', 'التمريض', 'الصيدلة', 'الجمال والجلدية', 'العلاج الطبيعي']
    countries = ['الأردن', 'مصر', 'السعودية', 'الإمارات', 'فلسطين']
    profile_images = [
        'https://i.pravatar.cc/150?u=1',
        'https://i.pravatar.cc/150?u=2',
        'https://i.pravatar.cc/150?u=3',
        'https://i.pravatar.cc/150?u=4',
        'https://i.pravatar.cc/150?u=5',
    ]
    for i, text in enumerate(texts):
        Testimonial.objects.create(
            user=random.choice(users['students']) if random.random() > 0.3 else None,
            name=f'مستخدم {i+1}',
            email=f'user{i+1}@example.com',
            specialty=specialties[i % len(specialties)],
            country=random.choice(countries),
            profile_image=profile_images[i % len(profile_images)],
            is_verified=random.choice([True, False]),
            content=text,
            rating=random.randint(3, 5),
            status=random.choice([Testimonial.PENDING, Testimonial.APPROVED]),
        )


ARTICLE_BODIES = [
    """<p>Preparing for a medical board exam can feel overwhelming, but the right strategy makes all the difference. In this guide, we share ten proven tips to help you study smarter, retain more information, and walk into exam day with confidence.</p>
<h2 id="start-early">Start Early and Build a Schedule</h2>
<p>Begin your preparation at least three months before the exam. A well-structured schedule helps you cover every topic without last-minute cramming.</p>
<ul><li>Break the syllabus into weekly milestones.</li><li>Reserve weekends for revision and practice tests.</li><li>Use a digital calendar with reminders.</li></ul>
<h2 id="active-learning">Use Active Learning Techniques</h2>
<p>Passive reading is not enough. Engage with the material through flashcards, summarization, and teaching others.</p>
<blockquote><p>"The best way to learn is to teach."</p></blockquote>
<h2 id="practice-tests">Take Regular Practice Tests</h2>
<p>Simulated exams identify weak areas and improve time management. Aim for at least one full-length test every two weeks.</p>
<figure><img src="https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=1200&q=80" alt="Student studying"><figcaption>Consistent practice builds confidence and speed.</figcaption></figure>
<h2 id="wellness">Prioritize Sleep and Nutrition</h2>
<p>Your brain needs rest and fuel. Avoid all-nighters and prioritize a balanced diet and regular exercise.</p>
<div class="info-box"><strong>Tip:</strong> Short walks during study breaks can boost memory retention.</div>
<h2 id="conclusion">Final Thoughts</h2>
<p>Success on exam day is the result of disciplined preparation. Start today, stay consistent, and trust the process.</p>""",
    """<p>Digital education is transforming how medical professionals learn. From virtual simulations to AI-powered tutoring, technology is making high-quality training accessible to everyone.</p>
<h2 id="online-platforms">The Rise of Online Learning Platforms</h2>
<p>Modern learners expect flexibility. Online platforms allow students to study anytime, anywhere, and at their own pace.</p>
<ul><li>On-demand video lectures</li><li>Interactive quizzes</li><li>Peer discussion forums</li></ul>
<h2 id="ai-tutors">AI Tutors and Personalized Feedback</h2>
<p>Artificial intelligence can analyze your performance and recommend the topics you need to review most.</p>
<pre><code>def study_recommendation(weak_topics):
    return "Focus on: " + ", ".join(weak_topics[:3])
</code></pre>
<h2 id="vr-simulations">Virtual Reality in Medical Training</h2>
<p>VR simulations offer safe, repeatable practice for procedures. Hospitals and universities are adopting these tools rapidly.</p>
<table><thead><tr><th>Technology</th><th>Benefit</th></tr></thead><tbody><tr><td>VR</td><td>Hands-on practice</td></tr><tr><td>AI</td><td>Personalized paths</td></tr><tr><td>Mobile</td><td>Learning on the go</td></tr></tbody></table>
<h2 id="conclusion">Looking Ahead</h2>
<p>The future of medical education is digital, personalized, and student-centered. Embracing these tools now will give learners a lasting advantage.</p>""",
    """<p>A study plan is your roadmap to success. Without one, it's easy to waste time on low-priority topics. Here is a simple framework to build a plan that works.</p>
<h2 id="assess">Assess Your Current Level</h2>
<p>Start with a diagnostic test to understand your strengths and weaknesses.</p>
<h2 id="goals">Set Clear Goals</h2>
<p>Define what you want to achieve each week. Goals should be specific, measurable, and realistic.</p>
<ol><li>Review all cardiac topics by week 3.</li><li>Complete 200 practice questions by week 5.</li><li>Score above 80% on two mock exams.</li></ol>
<h2 id="schedule">Build a Weekly Schedule</h2>
<p>Dedicate fixed time blocks to studying. Treat them like important appointments.</p>
<blockquote><p>"Plans are worthless, but planning is everything."</p></blockquote>
<h2 id="review">Review and Adjust</h2>
<p>Check your progress every Sunday. Adjust the next week based on what you accomplished.</p>""",
    """<p>Healthcare is evolving rapidly. Staying informed about the latest trends helps professionals remain relevant and deliver better care.</p>
<h2 id="telemedicine">Telemedicine Expansion</h2>
<p>Remote consultations have become a permanent part of healthcare delivery. Patients appreciate the convenience, and providers benefit from flexible workflows.</p>
<h2 id="data-analytics">Data-Driven Decision Making</h2>
<p>Hospitals are using analytics to predict patient outcomes, manage resources, and reduce costs.</p>
<div class="info-box"><strong>Insight:</strong> Predictive analytics can reduce readmission rates by up to 20%.</div>
<h2 id="prevention">Preventive Care Focus</h2>
<p>There is a global shift from treatment to prevention. Wellness programs and early screenings are gaining priority.</p>
<h2 id="conclusion">Conclusion</h2>
<p>Healthcare professionals who adapt to these trends will lead the future of medicine.</p>""",
    """<p>Medical training centers need effective marketing to attract students and partners. Here are strategies that deliver measurable results.</p>
<h2 id="content-marketing">Content Marketing</h2>
<p>Publish articles, guides, and videos that answer common student questions. This builds trust and improves search rankings.</p>
<ul><li>Blog regularly</li><li>Create video tutorials</li><li>Offer free webinars</li></ul>
<h2 id="social-proof">Social Proof</h2>
<p>Showcase testimonials, success stories, and accreditation badges prominently on your website.</p>
<h2 id="partnerships">Strategic Partnerships</h2>
<p>Partner with hospitals, universities, and industry bodies to expand your reach and credibility.</p>""",
    """<p>RootsExams is excited to announce a new partnership program designed to help training centers and educators deliver world-class exam preparation.</p>
<h2 id="program-overview">Program Overview</h2>
<p>Partners gain access to our full question bank, analytics dashboard, and co-branding opportunities.</p>
<h2 id="benefits">Benefits for Partners</h2>
<ul><li>Revenue sharing model</li><li>Marketing support</li><li>Dedicated account manager</li></ul>
<h2 id="how-to-apply">How to Apply</h2>
<p>Fill out the partnership form on our website. Our team will review your application within five business days.</p>""",
    """<p>Time management is a critical skill for medical students juggling classes, clinical rotations, and personal life.</p>
<h2 id="prioritize">Prioritize High-Impact Tasks</h2>
<p>Use the Eisenhower matrix to distinguish urgent from important tasks. Focus on what moves the needle.</p>
<table><thead><tr><th>Category</th><th>Action</th></tr></thead><tbody><tr><td>Urgent &amp; Important</td><td>Do first</td></tr><tr><td>Important, not Urgent</td><td>Schedule</td></tr><tr><td>Urgent, not Important</td><td>Delegate</td></tr><tr><td>Neither</td><td>Eliminate</td></tr></tbody></table>
<h2 id="techniques">Proven Techniques</h2>
<p>Pomodoro, time blocking, and batching tasks can dramatically improve focus and productivity.</p>
<h2 id="balance">Maintain Balance</h2>
<p>Burnout reduces long-term performance. Schedule downtime and hobbies alongside study blocks.</p>""",
    """<p>Artificial intelligence is reshaping exam preparation. From adaptive quizzes to instant feedback, AI helps students learn more efficiently.</p>
<h2 id="adaptive-learning">Adaptive Learning Paths</h2>
<p>AI systems adjust question difficulty based on your performance, keeping you in the optimal challenge zone.</p>
<h2 id="instant-feedback">Instant Feedback</h2>
<p>Immediate explanations help reinforce correct understanding and correct mistakes before they become habits.</p>
<blockquote><p>"Feedback is the breakfast of champions."</p></blockquote>
<h2 id="future">The Road Ahead</h2>
<p>As AI models improve, we expect even more personalized and immersive learning experiences.</p>""",
    """<p>Healthcare never stands still, and neither should professionals. Continuous learning is the key to career longevity and excellence.</p>
<h2 id="why">Why Continuous Learning Matters</h2>
<p>New treatments, technologies, and guidelines emerge constantly. Staying current ensures the best patient outcomes.</p>
<h2 id="how">How to Keep Learning</h2>
<ul><li>Attend conferences and workshops</li><li>Join professional networks</li><li>Enroll in online courses</li></ul>
<h2 id="conclusion">Conclusion</h2>
<p>Investing in your education is investing in your patients and your future.</p>""",
]


def create_blogs(main_cats):
    print('Creating blogs...')
    topics = ['Business', 'Technology', 'Education', 'Healthcare', 'Marketing', 'Company News']
    titles = [
        '10 Tips to Ace Your Medical Board Exam',
        'The Future of Digital Medical Education',
        'How to Build a Study Plan That Works',
        'Healthcare Trends Every Professional Should Know',
        'Marketing Strategies for Medical Training Centers',
        'RootsExams Announces New Partnership Program',
        'Effective Time Management for Medical Students',
        'The Role of AI in Modern Exam Preparation',
        'Why Continuous Learning Matters in Healthcare',
    ]
    images = [
        'https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=800&q=80',
        'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=800&q=80',
        'https://images.unsplash.com/photo-1503676260728-1c00da094a0b?auto=format&fit=crop&w=800&q=80',
        'https://images.unsplash.com/photo-1579684385127-1ef15d508118?auto=format&fit=crop&w=800&q=80',
        'https://images.unsplash.com/photo-1557804506-669a67965ba0?auto=format&fit=crop&w=800&q=80',
        'https://images.unsplash.com/photo-1556761175-5973dc0f32e7?auto=format&fit=crop&w=800&q=80',
        'https://images.unsplash.com/photo-1434030216411-0b793f4b4173?auto=format&fit=crop&w=800&q=80',
        'https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=800&q=80',
        'https://images.unsplash.com/photo-1532938911079-1b06ac7ceec7?auto=format&fit=crop&w=800&q=80',
    ]
    authors = ['Dr. Ahmad', 'Sara Al-Omari', 'Omar Haddad', 'Lina Nasser', 'RootsExams Team']
    author_titles = ['Chief Medical Officer', 'Learning Specialist', 'Product Manager', 'Content Lead', 'Editorial Team']
    author_images = [
        'https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?auto=format&fit=crop&w=200&q=80',
        'https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=200&q=80',
        'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=200&q=80',
        'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=200&q=80',
        'https://images.unsplash.com/photo-1560250097-0b93528c311a?auto=format&fit=crop&w=200&q=80',
    ]
    created_blogs = []
    for i, title in enumerate(titles):
        blog = Blog.objects.create(
            category=random.choice(main_cats),
            title=title,
            subtitle=f'A complete guide to {title.lower()} with practical advice and industry insights.',
            description=ARTICLE_BODIES[i % len(ARTICLE_BODIES)],
            image=images[i % len(images)],
            author=authors[i % len(authors)],
            author_title=author_titles[i % len(author_titles)],
            author_image=author_images[i % len(author_images)],
            topic=random.choice(topics),
            reading_time=random.randint(4, 12),
            views=random.randint(100, 5000),
            tags=','.join(random.sample(['Study Tips', 'Exams', 'Healthcare', 'Technology', 'Career', 'News', 'Education'], k=3)),
            status=Blog.ACTIVE,
        )
        created_blogs.append(blog)

    # Add sample approved comments to the first few blogs
    print('Creating blog comments...')
    comment_names = ['Ahmad K.', 'Layla M.', 'Mohammad S.', 'Noor H.', 'Rami T.']
    for blog in created_blogs[:4]:
        for _ in range(random.randint(1, 3)):
            BlogComment.objects.create(
                blog=blog,
                name=random.choice(comment_names),
                email=f'{random.choice(["user", "reader", "student"])}{random.randint(1,999)}@example.com',
                content='Great article! Very helpful and well explained. I will definitely apply these tips.',
                status=BlogComment.APPROVED,
            )


def create_support_requests(users, questions):
    print('Creating support requests...')
    statuses = [SupportRequest.STATUS_OPEN, SupportRequest.STATUS_CLOSED]
    for i in range(5):
        q = random.choice(questions)
        SupportRequest.objects.create(
            user=random.choice(users['students']),
            question=q,
            question_text=q.text_question,
            message=f'استفسار رقم {i+1} حول هذا السؤال.',
            status=random.choice(statuses),
        )


def create_instructors(main_cats):
    print('Creating instructors...')
    created = []
    instructors_data = [
        {
            'name': 'د. أحمد الخالدي',
            'title': 'استشاري الطب الباطني',
            'specialization': 'طب بشري',
            'bio': 'أكثر من 15 عاماً من الخبرة في تدريس الاختبارات الطبية وإعداد الأطباء للبورد.',
            'years': 15,
            'students': 12400,
            'courses': 8,
            'certificates': 3200,
            'rate': Decimal('4.9'),
            'featured': True,
        },
        {
            'name': 'د. سارة العمري',
            'title': 'مهندسة مدنية ومدربة معتمدة',
            'specialization': 'هندسة مدنية',
            'bio': 'تخصص في تبسيط مفاهيم الهندسة للاختبارات المهنية مع آلاف الطلاب الناجحين.',
            'years': 10,
            'students': 8700,
            'courses': 6,
            'certificates': 2100,
            'rate': Decimal('4.8'),
            'featured': True,
        },
        {
            'name': 'د. محمد السعدي',
            'title': 'صيدلي إكلينيكي',
            'specialization': 'صيدلة',
            'bio': 'خبير في التدريب الصيدلي الإكلينيكي وإعداد المتخصصين لاختبارات الترخيص.',
            'years': 12,
            'students': 9300,
            'courses': 5,
            'certificates': 1800,
            'rate': Decimal('4.7'),
            'featured': True,
        },
        {
            'name': 'د. لينا ناصر',
            'title': 'أخصائية التمريض السريري',
            'specialization': 'تمريض',
            'bio': 'مدربة شغوفة بتمكين الممرضين من اجتياز الاختبارات التخصصية بثقة.',
            'years': 8,
            'students': 5600,
            'courses': 4,
            'certificates': 1200,
            'rate': Decimal('4.6'),
            'featured': False,
        },
        {
            'name': 'م. عمر حداد',
            'title': 'مهندس برمجيات',
            'specialization': 'تقنية المعلومات',
            'bio': 'مدرب معتمد في برمجة وتطوير الأنظمة الرقمية للمهنيين والطلبة.',
            'years': 9,
            'students': 6100,
            'courses': 7,
            'certificates': 1500,
            'rate': Decimal('4.5'),
            'featured': False,
        },
        {
            'name': 'د. رنا الشيخ',
            'title': 'اختصاصية أمراض الجلدية والتجميل',
            'specialization': 'الجمال والجلدية',
            'bio': 'تقدم محتوى تدريبي احترافي في مجال الجلدية والتجميل للاختبارات المهنية.',
            'years': 11,
            'students': 7200,
            'courses': 5,
            'certificates': 1900,
            'rate': Decimal('4.8'),
            'featured': False,
        },
    ]
    images = [
        'https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?auto=format&fit=crop&w=400&q=80',
        'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=400&q=80',
        'https://images.unsplash.com/photo-1560250097-0b93528c311a?auto=format&fit=crop&w=400&q=80',
        'https://images.unsplash.com/photo-1559839734-2b71ea197ec2?auto=format&fit=crop&w=400&q=80',
        'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=400&q=80',
        'https://images.unsplash.com/photo-1594824476967-48c8b964273f?auto=format&fit=crop&w=400&q=80',
    ]
    social_domains = ['facebook.com', 'twitter.com', 'linkedin.com']
    for i, item in enumerate(instructors_data):
        instructor = Instructor.objects.create(
            name=item['name'],
            title=item['title'],
            image=images[i % len(images)],
            specialization=item['specialization'],
            category=random.choice(main_cats),
            bio=item['bio'],
            years_of_experience=item['years'],
            students_count=item['students'],
            courses_count=item['courses'],
            certificates_count=item['certificates'],
            rate=item['rate'],
            facebook=f'https://{random.choice(social_domains)}/instructor-{i+1}',
            twitter=f'https://{random.choice(social_domains)}/instructor-{i+1}',
            linkedin=f'https://{random.choice(social_domains)}/instructor-{i+1}',
            is_featured=item['featured'],
            order=i + 1,
            status=Instructor.ACTIVE,
        )
        created.append(instructor)
    return created


def create_faqs():
    print('Creating FAQs...')
    faqs = [
        ('كيف يتم اختيار المدربين في المنصة؟', 'نختار المدربين بناءً على خبرتهم العملية والأكاديمية، مع التأكد من سجلهم في إعداد المتعلمين للنجاح.', 'instructors'),
        ('هل يمكنني التواصل مباشرة مع المدرب؟', 'نعم، يمكنك طرح الأسئلة ضمن كل درس أو عبر قسم الدعم الفني.', 'instructors'),
        ('هل الدورات معتمدة؟', 'جميع دوراتنا مصممة وفق معايير مهنية وتقدم شهادات إتمام معتمدة.', 'certificates'),
        ('كيف أصبح مدرباً في المنصة؟', 'يمكنك التقدم عبر نموذج الانضمام وسيقوم فريقنا بمراجعة طلبك.', 'instructors'),
        ('هل هناك ضمان لاسترجاع المبلغ؟', 'نقدم فترة تجريبية مجانية لمعظم الباقات، وسياسة استرجاع واضحة خلال 7 أيام.', 'general'),
    ]
    for i, (q, a, cat) in enumerate(faqs):
        Faq.objects.create(question=q, answer=a, category=cat, order=i + 1, status=Faq.ACTIVE)


def create_ai_instructions(questions):
    print('Creating AI instructions...')
    for q in random.sample(questions, min(5, len(questions))):
        AiInstruction.objects.create(
            question=q,
            instructions='إرشادات للذكاء الاصطناعي لشرح هذا السؤال.',
            is_default=random.random() > 0.5,
        )


def create_discount_codes():
    print('Creating discount codes...')
    today = timezone.now().date()
    DiscountCode.objects.create(
        code='ROOTS20', marketer='أحمد', type=DiscountCode.TYPE_PERCENTAGE,
        percentage=Decimal('20.00'), quantity=100, used_count=5,
        from_date=today - timedelta(days=10), to_date=today + timedelta(days=20),
        status=DiscountCode.STATUS_ACTIVE,
    )
    DiscountCode.objects.create(
        code='SAVE5', marketer='سارة', type=DiscountCode.TYPE_AMOUNT,
        amount=Decimal('5.00'), quantity=50, used_count=2,
        from_date=today - timedelta(days=5), to_date=today + timedelta(days=30),
        status=DiscountCode.STATUS_ACTIVE,
    )


def create_payment_types():
    print('Creating payment types...')
    types = [
        PaymentType.objects.get_or_create(name='Visa / Mastercard')[0],
        PaymentType.objects.get_or_create(name='PayPal')[0],
    ]
    return types


def create_app_info():
    print('Creating app info...')
    AppInfo.objects.get_or_create(
        defaults={
            'ios_version': '1.2.0',
            'android_version': '1.2.0',
            'map_url': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3387.014928858122!2d35.910597315116!3d31.949351981229!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x151b5f8ba1e0b6c3%3A0x3c5c5c5c5c5c5c5c!2sAmman!5e0!3m2!1sen!2sjo!4v1600000000000!5m2!1sen!2sjo',
            'address': 'عمّان، الأردن — الحي الطبي، مبنى 12',
            'phone': '+962 79 123 4567',
            'whatsapp': '+962 79 123 4567',
            'email': 'info@rootsexams.com',
            'working_hours': 'الأحد - الخميس: 9:00 ص - 6:00 م',
        }
    )


def create_partners():
    print('Creating partners...')
    partners = [
        ('Ministry of Health', 'https://placehold.co/200x80/002770/ffffff?text=MOH', 'https://www.moh.gov.jo'),
        ('Jordan Medical Association', 'https://placehold.co/200x80/06bfb0/ffffff?text=JMA', 'https://www.jma.org.jo'),
        ('Royal Medical Services', 'https://placehold.co/200x80/2563eb/ffffff?text=RMS', 'https://www.rms.gov.jo'),
        ('Arab Medical Union', 'https://placehold.co/200x80/16a34a/ffffff?text=AMU', 'https://www.amu.org'),
        ('WHO EMRO', 'https://placehold.co/200x80/f59e0b/ffffff?text=WHO', 'https://www.emro.who.int'),
        ('UNICEF Jordan', 'https://placehold.co/200x80/7c3aed/ffffff?text=UNICEF', 'https://www.unicef.org/jordan'),
    ]
    for i, (name, logo, url) in enumerate(partners):
        Partner.objects.get_or_create(
            name=name,
            defaults={
                'logo': logo,
                'website_url': url,
                'order': i,
                'status': Partner.ACTIVE,
            }
        )


def create_settings():
    print('Creating settings...')
    defaults = {
        'support_phone': '+962790000000',
        'contact_email': 'support@rootsexams.com',
        'max_trials_per_day': '3',
        'enable_registration': '1',
    }
    for key, value in defaults.items():
        Setting.objects.get_or_create(key=key, defaults={'value': value})


def seed(clear=False):
    if clear:
        clear_existing_data()
    else:
        if Category.objects.exists() or User.objects.filter(role_type=User.ROLE_USER).exists():
            print('Demo data already exists. Run with --clear to reset.')
            return

    with transaction.atomic():
        users = create_users()
        main_cats, sub_cats, sub_sub_cats = create_categories()
        topics, sections = create_topics_and_sections(main_cats, sub_cats)
        questions = create_questions(main_cats, sub_cats, sub_sub_cats, topics, sections)
        exams = create_exams(main_cats, sub_cats, questions)
        payment_types = create_payment_types()
        create_notifications(users)
        create_testimonials(users)
        create_blogs(main_cats)
        create_support_requests(users, questions)
        instructors = create_instructors(main_cats)
        create_faqs()
        create_ai_instructions(questions)
        packages = create_packages(main_cats, exams, instructors)
        create_discount_codes()
        create_subscriptions_payments_invoices(users, packages, payment_types)
        create_app_info()
        create_partners()
        create_settings()

    print('\nSeed completed successfully.')
    print('\nLogin credentials:')
    print('  Admin      : +962790000001 / admin123')
    print('  Accountant : +962790000003 / accountant123')
    print('  Data Entry : +962790000004 / dataentry123')
    print(f'  Students   : +962791000100 ... +962791000109 / {STUDENT_PASSWORD}')


def main():
    parser = argparse.ArgumentParser(description='Seed RootsExams platform with demo data.')
    parser.add_argument('--clear', action='store_true', help='Delete existing demo data before seeding.')
    args = parser.parse_args()
    seed(clear=args.clear)


if __name__ == '__main__':
    main()
