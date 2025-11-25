from django import forms
from .models import Flashcard, Category
from .models import PDFDocument

class PDFUploadForm(forms.ModelForm):
    class Meta:
        model = PDFDocument
        fields = ['title', 'pdf_file']

class FlashcardForm(forms.ModelForm):
    category_name = forms.CharField(label='Category', max_length=100)

    class Meta:
        model = Flashcard
        fields = [
            'question',
            'answer',
            'option_a', 'option_b', 'option_c', 'option_d', 'correct_option',
        ]

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
