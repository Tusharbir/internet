from pathlib import Path

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils.text import slugify

from .models import Category, Item, Message, Report, User


# report form
class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['reason', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional details...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'reason':
                field.widget.attrs.setdefault('class', 'form-select')
                field.widget.attrs.setdefault('autocomplete', 'off')
            else:
                field.widget.attrs.setdefault('class', 'form-control')
                field.widget.attrs.setdefault('autocomplete', 'off')


# multiple fil input and field to handle multiple image uploads 
class MultiFileInput(forms.FileInput):
    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        if hasattr(files, 'getlist'):
            upload = files.getlist(name)
        else:
            upload = files.get(name)
            if upload:
                upload = [upload]
            else:
                upload = []
        return upload if upload else []
    
# user registration form 
class UserRegistrationForm(UserCreationForm):
    university_email = forms.EmailField(required=True, help_text='Use your @uwindsor.ca email.')
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
            field.widget.attrs.setdefault('class', 'form-control')
            if field_name in {'password1', 'password2'}:
                field.widget.attrs.setdefault('autocomplete', 'new-password')
            elif field_name == 'username':
                field.widget.attrs.setdefault('autocomplete', 'username')
            else:
                field.widget.attrs.setdefault('autocomplete', 'off')

    def clean_university_email(self):
        email = (self.cleaned_data.get('university_email') or '').strip().lower()
        if not email:
            raise forms.ValidationError('University email is required.')
        if not email.endswith('@uwindsor.ca'):
            raise forms.ValidationError('Please use your @uwindsor.ca email address.')
        return email




class MultiFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultiFileInput(attrs={'multiple': True, 'accept': 'image/*'}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if not data or data == []:
            if self.required:
                raise forms.ValidationError(self.error_messages['required'])
            return []
        result = []
        for item in data:
            result.append(super().clean(item, initial))
        return result


class ItemForm(forms.ModelForm):
    images = MultiFileField(
        required=False,
        help_text='You can upload up to 6 images (JPG, PNG, WebP).',
    )
    delete_images = forms.CharField(required=False, widget=forms.HiddenInput())

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'negotiable':
                field.widget.attrs.setdefault('class', 'form-check-input')
            elif field_name in ('status', 'condition', 'category'):
                field.widget.attrs.setdefault('class', 'form-select')
            elif field_name == 'delete_images':
                pass
            else:
                field.widget.attrs.setdefault('class', 'form-control')

        if self.instance.pk and self.instance.status == Item.STATUS_SOLD:
            self.fields['status'].choices = [(Item.STATUS_SOLD, 'Sold')]
            self.fields['status'].disabled = True
        elif self.instance.pk:
            self.fields['status'].choices = [
                (Item.STATUS_DRAFT, 'Draft'),
                (Item.STATUS_PUBLISHED, 'Published'),
            ]
        else:
            self.fields['status'].choices = [
                (Item.STATUS_DRAFT, 'Draft'),
                (Item.STATUS_PUBLISHED, 'Published'),
            ]
        self.fields['title'].help_text = 'Use a clear title between 5 and 80 characters.'
        self.fields['description'].help_text = 'Add at least 20 characters with relevant details.'
        self.fields['price'].help_text = 'Enter a price of $0 or more.'
        self.fields['location'].help_text = 'Add a meetup spot or area on campus.'

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
 
    def clean_images(self): 
        images = self.cleaned_data.get('images') or [] 
        allowed_types = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'} 
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif'} 
        for img in images: 
            extension = Path(img.name).suffix.lower() 
            if extension not in allowed_extensions: 
                raise forms.ValidationError( 
                    f'"{img.name}" has an unsupported file extension. Allowed: JPG, PNG, WebP, GIF.' 
                ) 
            if img.content_type not in allowed_types: 
                raise forms.ValidationError( 
                    f'"{img.name}" is not a valid image. Allowed: JPG, PNG, WebP, GIF.' 
                ) 
            if img.size > 5 * 1024 * 1024: 
                raise forms.ValidationError( 
                    f'"{img.name}" exceeds the 5 MB limit.' 
                ) 
        return images 
 
    def clean(self): 
        cleaned_data = super().clean() 
        images = cleaned_data.get('images') or [] 
        delete_ids = self.cleaned_data.get('delete_images', '') 
        delete_count = 0 
        if delete_ids: 
            raw_ids = [x.strip() for x in delete_ids.split(',') if x.strip()] 
            if not all(item_id.isdigit() for item_id in raw_ids): 
                raise forms.ValidationError('One or more selected images could not be removed.') 
            delete_count = len(raw_ids) 
 
        if self.instance.pk: 
            existing_count = max(self.instance.images.count() - delete_count, 0) 
        else:
            existing_count = 0 

        total_images = len(images) + existing_count 
        if total_images == 0:
            raise forms.ValidationError('Please upload at least 1 image.') 
        if total_images > 6:
            raise forms.ValidationError('You can only have up to 6 images per listing.') 
        return cleaned_data
 

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
            field.widget.attrs.setdefault('autocomplete', 'off')

# admin filter forms for items, reports, users, and messages
class AdminItemFilterForm(forms.Form):
    q = forms.CharField(required=False, label='Search')
    status = forms.ChoiceField(
        choices=[('', 'All statuses')] + Item.STATUS_CHOICES,
        required=False,
    )
    category = forms.ModelChoiceField(queryset=None, required=False, empty_label='All categories')
    reported = forms.ChoiceField(
        choices=[
            ('', 'All listings'),
            ('reported', 'Reported only'),
            ('clean', 'No reports'),
        ],
        required=False,
    )

class AdminReportFilterForm(forms.Form):
    q = forms.CharField(required=False, label='Search')
    status = forms.ChoiceField(
        choices=[('', 'All statuses')] + Report.STATUS_CHOICES,
        required=False,
    )
    reason = forms.ChoiceField(
        choices=[('', 'All reasons')] + Report.REASON_CHOICES,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.ChoiceField):
                field.widget.attrs.setdefault('class', 'form-select')
            else:
                field.widget.attrs.setdefault('class', 'form-control')

    def __init__(self, *args, **kwargs):
        categories = kwargs.pop('categories', None)
        super().__init__(*args, **kwargs)
        if categories is not None:
            self.fields['category'].queryset = categories
        for field in self.fields.values():
            if isinstance(field, forms.ModelChoiceField) or isinstance(field, forms.ChoiceField):
                field.widget.attrs.setdefault('class', 'form-select')
            else:
                field.widget.attrs.setdefault('class', 'form-control')




class AdminUserFilterForm(forms.Form):
    q = forms.CharField(required=False, label='Search')
    role = forms.ChoiceField(
        choices=[
            ('', 'All users'),
            ('staff', 'Staff only'),
            ('member', 'Marketplace members'),
            ('inactive', 'Inactive only'),
        ],
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.ChoiceField):
                field.widget.attrs.setdefault('class', 'form-select')
            else:
                field.widget.attrs.setdefault('class', 'form-control')


class AdminMessageFilterForm(forms.Form):
    q = forms.CharField(required=False, label='Search')
    read_state = forms.ChoiceField(
        choices=[
            ('', 'All messages'),
            ('unread', 'Unread only'),
            ('read', 'Read only'),
        ],
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.ChoiceField):
                field.widget.attrs.setdefault('class', 'form-select')
            else:
                field.widget.attrs.setdefault('class', 'form-control')


class CategoryAdminForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'slug']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def clean_name(self):
        return self.cleaned_data['name'].strip()

    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').strip()
        if slug:
            return slug
        name = self.cleaned_data.get('name', '')
        return slugify(name)
