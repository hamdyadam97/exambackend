# Backend App Responsibilities

This document clarifies the ownership of each Django app in `backend/apps/`. Keeping responsibilities narrow makes the codebase easier to navigate, test, and extend.

## `core`
**Cross-cutting infrastructure that does not belong to a domain.**

- URL routing (`core/urls.py`) — wires all app views together.
- Reusable utilities (`api_response`, `send_response`, `send_error`, pagination, middleware).
- Thin service wrappers for third-party integrations (HyperPay, OpenAI).
- No models. Should not contain business rules.

## `users`
**Identity, authentication, and user-scoped audit data.**

- Custom user model (`User`) with mobile-based authentication.
- User profile, OTP, password reset tokens.
- Audit log for sensitive operations.
- Convenience methods on `User` for subscriptions/category access (`subscribed_categories`, `subscribed_sub_categories`, etc.).

## `content`
**Educational content hierarchy and supporting CMS data.**

- Self-referential `Category` tree (replaces legacy `Category`/`SubCategory`/`SubSubCategory`).
- Topics (`QuestionsTopic`), exam sections (`ExamSection`).
- Blogs, testimonials, instructors, notifications, app info, settings, contact/support messages, AI instructions.
- Exposes serializers used by `exams` and `packages`.

## `exams`
**Question bank and exam-taking lifecycle.**

- `Question` / `Answer` and their relationships to topics/sections.
- `Exam` definitions and `UserExam` attempts.
- `ExamTrail` (trial/exam sessions) with staged questions and `ExamTrialDetail` answers.
- Reporting per category/sub-category/section/topic.
- No category definitions; consumes `content.Category`.

## `packages`
**Subscriptions, packages, and discount codes.**

- `Package` (pricing, duration, question limits).
- `PackageSubCategory` / `PackageExam` linking packages to content and exams.
- `UserPackage` subscriptions.
- `DiscountCode` and coupon validation.
- No payment processing; delegates payments to `payments`.

## `payments`
**Payment records and transaction history.**

- Payment types, HyperPay transactions, money logs.
- Stored card tokens (vault-style).
- Invoices.
- Tied to `users.User` and `packages.UserPackage` but does not own subscriptions.

---

## Dependency Direction

```
users  ←  packages  ←  payments
           ↑
content ←  exams
```

- `content` is the base domain for educational hierarchy.
- `exams` and `packages` depend on `content` and `users`.
- `payments` depends on `users` and `packages`.
- `core` depends on all apps only for URL wiring.
