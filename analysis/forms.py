import gzip
from importlib import import_module
from pathlib import Path
from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class UploadFileForm(forms.Form):
    file = forms.FileField()

class CustomPasswordChangeForm(PasswordChangeForm):
    error_messages = {
        'password_incorrect': "현재 비밀번호가 잘못되었습니다. 다시 시도해주세요.",
        'password_mismatch': "비밀번호가 일치하지 않습니다.",
    }
    DEFAULT_PASSWORD_LIST_PATH = Path(import_module('django.contrib.auth').__file__).resolve().parent / 'common-passwords.txt.gz'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].error_messages['required'] = '현재 비밀번호를 입력해주세요.'
        self.fields['new_password1'].error_messages['required'] = '새로운 비밀번호를 입력해주세요.'
        self.fields['new_password2'].error_messages['required'] = '비밀번호 확인을 입력해주세요.'

        try:
            with gzip.open(self.DEFAULT_PASSWORD_LIST_PATH, 'rt', encoding='utf-8') as f:
                self.common_passwords = {x.strip() for x in f}
        except OSError:
            with open(self.DEFAULT_PASSWORD_LIST_PATH) as f:
                self.common_passwords = {x.strip() for x in f}

    def clean_new_password1(self):
        password1 = self.cleaned_data.get('new_password1')
        if len(password1) < 8:
            raise ValidationError("비밀번호는 최소 8자 이상이어야 합니다.")
        if password1.isdigit():
            raise ValidationError("비밀번호는 숫자로만 구성될 수 없습니다.")
        if password1.lower() in self.common_passwords:
            raise ValidationError("너무 흔한 비밀번호는 사용할 수 없습니다.")

        return password1

    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if len(password2) < 8:
            raise ValidationError("")
        if password2.isdigit():
            raise ValidationError("")
        if password2.lower() in self.common_passwords:
            raise ValidationError("")
        if password1 and password2 and password1 != password2:
            raise ValidationError("비밀번호가 일치하지 않습니다.")

        return password2
