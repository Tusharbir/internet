from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.forms.widgets import ClearableFileInput

from .models import Item, Message, Report, User


class UserRegistrationForm(UserCreationForm):
    university_email = forms.EmailField(required=False)
    student_id = forms.CharField(required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            'username',
            'first_name',
            'last_name',
            'email',
            'university_email',
            'student_id',
            'password1',
            'password2',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'negotiable':
                field.widget.attrs.setdefault('class', 'form-check-input')
            elif field_name == 'status':
                field.widget.attrs.setdefault('class', 'form-select')
            else:
                field.widget.attrs.setdefault('class', 'form-control')
        if 'status' in self.fields:
            if self.instance.pk and self.instance.status == Item.STATUS_SOLD:
                self.fields['status'].choices = [(Item.STATUS_SOLD, 'Sold')]
                self.fields['status'].disabled = True
            else:
                self.fields['status'].choices = [
                    (Item.STATUS_DRAFT, 'Draft'),
                    (Item.STATUS_PUBLISHED, 'Published'),
                ]


class MultiFileInput(ClearableFileInput):
    allow_multiple_selected = True


class ItemForm(forms.ModelForm):
    images = forms.FileField(
        required=False,
        widget=MultiFileInput(attrs={'multiple': True}),
        help_text='You can upload multiple images.',
    )

    class Meta:
        model = Item
        fields = [
            'title',
            'description',
            'price',
            'condition',
            'category',
            'location',
            'negotiable',
            'status',
        ]

    def clean_title(self):
        title = self.cleaned_data['title'].strip()
        if not 5 <= len(title) <= 80:
            raise forms.ValidationError('Title must be between 5 and 80 characters.')
        return title

    def clean_description(self):
        description = self.cleaned_data['description'].strip()
        if len(description) < 20:
            raise forms.ValidationError('Description must be at least 20 characters.')
        return description

    def clean_price(self):
        price = self.cleaned_data['price']
        if price is not None and price < 0:
            raise forms.ValidationError('Price must be zero or greater.')
        return price

    def clean(self):
        cleaned_data = super().clean()
        images = self.files.getlist('images')
        if self.instance.pk:
            has_existing = self.instance.images.exists()
        else:
            has_existing = False
        total_images = len(images) + (self.instance.images.count() if has_existing else 0)
        if not images and not has_existing:
            raise forms.ValidationError('Please upload at least 1 image.')
        if images and not 1 <= len(images) <= 6:
            raise forms.ValidationError('Please upload between 1 and 6 images.')
        if total_images > 6:
            raise forms.ValidationError('You can only have up to 6 images per listing.')
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class ItemFilterForm(forms.Form):
    q = forms.CharField(required=False, label='Search')
    category = forms.ModelChoiceField(queryset=None, required=False)
    condition = forms.ChoiceField(
        choices=[('', 'Any condition')] + Item.CONDITION_CHOICES,
        required=False,
    )
    min_price = forms.DecimalField(required=False, min_value=0, decimal_places=2)
    max_price = forms.DecimalField(required=False, min_value=0, decimal_places=2)
    sort = forms.ChoiceField(
        choices=[
            ('newest', 'Newest'),
            ('price_low', 'Lowest price'),
            ('price_high', 'Highest price'),
        ],
        required=False,
    )

    def __init__(self, *args, **kwargs):
        categories = kwargs.pop('categories', None)
        super().__init__(*args, **kwargs)
        if categories is not None:
            self.fields['category'].queryset = categories
        for field_name, field in self.fields.items():
            if field_name in {'category', 'condition', 'sort'}:
                field.widget.attrs.setdefault('class', 'form-select')
            else:
                field.widget.attrs.setdefault('class', 'form-control')


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['body']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Write your message...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['reason', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional details...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')
