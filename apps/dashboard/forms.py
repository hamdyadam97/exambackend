from django import forms
from apps.users.models import User
from apps.content.models import Category
from apps.dashboard.arabic import to_arabic


class BaseDashboardForm(forms.ModelForm):
    """Base form that adds Tailwind classes and Arabic labels to every widget."""

    base_class = (
        'admin-input w-full rounded-lg border border-slate-200 dark:border-slate-700 '
        'bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-100 '
        'px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 '
        'transition placeholder:text-slate-400'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.label = to_arabic(field.label)
            if field.help_text:
                field.help_text = to_arabic(field.help_text)

            # Translate simple choice labels
            if hasattr(field, 'choices') and field.choices:
                new_choices = []
                for value, label in field.choices:
                    new_choices.append((value, to_arabic(label)))
                field.choices = new_choices

            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault(
                    'class',
                    'w-5 h-5 rounded border-slate-300 text-brand-600 focus:ring-brand-500 dark:border-slate-600 dark:bg-slate-800'
                )
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault('class', self.base_class)
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault(
                    'class',
                    self.base_class + ' admin-textarea'
                )
            elif isinstance(widget, forms.DateInput):
                widget.attrs.setdefault('type', 'date')
                widget.attrs.setdefault('class', self.base_class)
            elif isinstance(widget, forms.DateTimeInput):
                widget.attrs.setdefault('class', self.base_class)
            elif isinstance(widget, forms.FileInput):
                widget.attrs.setdefault(
                    'class',
                    'block w-full text-sm text-slate-600 dark:text-slate-300 '
                    'file:me-4 file:py-2 file:px-4 file:rounded-lg file:border-0 '
                    'file:text-sm file:font-medium file:bg-brand-50 file:text-brand-700 '
                    'hover:file:bg-brand-100'
                )
            else:
                widget.attrs.setdefault('class', self.base_class)


class UserDashboardForm(BaseDashboardForm):
    """User form that works for both create and update."""

    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput,
        required=False,
    )
    password2 = forms.CharField(
        label='Confirm password',
        widget=forms.PasswordInput,
        required=False,
    )

    class Meta:
        model = User
        fields = [
            'phone', 'first_name', 'last_name', 'email',
            'role_type', 'status', 'is_staff', 'is_superuser',
            'is_phone_verified', 'is_email_verified',
        ]

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 or p2:
            if p1 != p2:
                self.add_error('password2', 'كلمتا المرور غير متطابقتين.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password1')
        if password:
            user.set_password(password)
        if commit:
            user.save()
            self.save_m2m()
        return user


class CategoryForm(BaseDashboardForm):
    """Category form with parent restricted by level."""

    class Meta:
        model = Category
        exclude = ['created_at', 'updated_at', 'deleted_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter parent choices based on the instance level when editing.
        level = self.instance.level if self.instance and self.instance.pk else None
        if level and level > 1:
            self.fields['parent'].queryset = Category.objects.filter(level=level - 1, status=Category.ACTIVE)
        else:
            self.fields['parent'].queryset = Category.objects.filter(status=Category.ACTIVE)
        self.fields['parent'].required = False

    def clean(self):
        cleaned = super().clean()
        level = cleaned.get('level')
        parent = cleaned.get('parent')
        if level and level > 1 and not parent:
            self.add_error('parent', 'يجب اختيار تصنيف أب لهذا المستوى.')
        if parent and parent.level != level - 1:
            self.add_error('parent', 'التصنيف الأب يجب أن يكون من المستوى السابق.')
        return cleaned
