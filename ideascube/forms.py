from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _


class UserForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field, forms.DateField):
                # Force date format on load, so date picker doesn't mess it up
                # because of i10n.
                field.widget = forms.DateInput(format='%Y-%m-%d')

    class Meta:
        model = get_user_model()
        exclude = ['password', 'last_login', 'is_staff']


class CreateStaffForm(forms.ModelForm):
    serial = forms.CharField(label=_('Username'),
                             help_text="Spaces are not allowed")
    password = forms.CharField(label=_("Password"),
                               help_text=_('To create a strong password, '
                                           'forget about passwords, and think '
                                           'rather about a passphrase. For '
                                           'instance: "The boat is flowing on '
                                           'the water" is a strong and easy to'
                                           ' remember passphrase. Now choose '
                                           'your own passphrase!'),
                               widget=forms.PasswordInput)
    password_confirm = forms.CharField(label=_("Confirm password"),
                                       widget=forms.PasswordInput)

    class Meta:
        model = get_user_model()
        fields = ['serial', 'password']

    def clean_password_confirm(self):
        password1 = self.cleaned_data.get('password')
        password2 = self.cleaned_data.get('password_confirm')
        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError('The two passwords do not match')
        return password2

    def save(self, *args, **kwargs):
        user = super(CreateStaffForm, self).save(*args, **kwargs)
        password = self.cleaned_data['password']
        user.set_password(password)
        user.is_staff = True
        user.save()
        return user
