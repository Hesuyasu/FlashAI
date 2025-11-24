from datetime import timedelta
from django.utils import timezone
from .models import Flashcard, Category, PDFDocument
from .utils import extract_text_from_pdf, generate_flashcards_with_ai
from django.shortcuts import render, get_object_or_404, redirect
from .forms import FlashcardForm, CategoryForm, PDFUploadForm
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from .models import Flashcard


@login_required(login_url='/account/login/')
def home(request):
    return render(request, 'home.html')

def upload_pdf(request):
    """Handle PDF upload, extract text, generate AI flashcards, and persist.

    Workflow:
      1. User uploads a PDF with a title and (optional) category string.
      2. Save PDFDocument instance.
      3. Extract text via PyPDF2 (if available).
      4. Generate flashcards using AI or fallback heuristic.
      5. Create Flashcard objects under chosen/created Category.
    """
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_instance = form.save()  # Save PDFDocument

            # Category selection from raw POST (not part of ModelForm)
            category_name = request.POST.get('category') or 'Other'
            category_obj, _ = Category.objects.get_or_create(name=category_name)

            # Open the stored file for text extraction
            pdf_file_field = pdf_instance.pdf_file
            try:
                pdf_file_field.open('rb')
                extracted_text = extract_text_from_pdf(pdf_file_field)
            finally:
                try:
                    pdf_file_field.close()
                except Exception:
                    pass

            flashcards_data = generate_flashcards_with_ai(extracted_text)

            for card in flashcards_data:
                question = card.get('question', '').strip()[:255]
                answer = card.get('answer', '').strip()
                if question and answer:
                    Flashcard.objects.create(
                        question=question,
                        answer=answer,
                        category=category_obj
                    )
            return redirect('flashcard_list')
    else:
        form = PDFUploadForm()

    pdfs = PDFDocument.objects.order_by('-uploaded_at')
    return render(request, 'upload_pdf.html', {
        'form': form,
        'pdf_list': pdfs,
    })


class HomePageView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"
    login_url = '/accounts/login/'
    redirect_field_name = 'next'

@login_required(login_url='/accounts/login/')
def home(request):
    total_flashcards = Flashcard.objects.count()
    pdf_count = PDFDocument.objects.count() 
    new_this_week = Flashcard.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=7)
    ).count()
    return render(request, 'home.html', {
        'flashcard_count': total_flashcards,
        'pdf_count': pdf_count, 
        'new_this_week': new_this_week,
    })


def create_flashcard(request):
    if request.method == 'POST':
        form = FlashcardForm(request.POST)
        if form.is_valid():
            category_name = form.cleaned_data['category_name']
            category, created = Category.objects.get_or_create(name=category_name)
            flashcard = Flashcard(
                question=form.cleaned_data['question'],
                answer=form.cleaned_data['answer'],
                category=category
            )
            flashcard.save()
            return redirect('flashcard_list')
    else:
        form = FlashcardForm()

    return render(request, 'create_flashcard.html', {'form': form})




#def collection_history(request):
#    flashcards = Flashcard.objects.order_by('-created_at')
#    return render(request, 'collection_history.html', {'flashcards': flashcards})


def flashcard_list(request):
    flashcards = Flashcard.objects.all()
    return render(request, 'flashcard_list.html', {'flashcards': flashcards})


def flashcard_update(request, pk):
    flashcard = get_object_or_404(Flashcard, pk=pk)  # user=request.user
    form = FlashcardForm(request.POST or None, instance=flashcard)
    if form.is_valid():
        form.save()
        return redirect('flashcard_list')
    return render(request, 'flashcards/flashcard_form.html', {'form': form})


def flashcard_delete(request, pk):
    flashcard = get_object_or_404(Flashcard, pk=pk)  # user=request.user
    if request.method == 'POST':
        flashcard.delete()
        return redirect('flashcard_list')
    return render(request, 'flashcards/flashcard_confirm_delete.html', {'flashcard': flashcard})

def create_category(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('create_flashcard')
    else:
        form = CategoryForm()
    categories = Category.objects.order_by('name')
    return render(request, "create_category.html", {"form": form, "categories": categories})


def delete_category(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.delete()
    return redirect('create_category')


def api_flashcard_count(request):
    count = Flashcard.objects.count()
    return JsonResponse({'count': count})


def study_flashcards(request):
    selected_category_id = request.GET.get('category')
    categories = Category.objects.all()
    if selected_category_id:
        flashcards_qs = Flashcard.objects.filter(
            category_id=selected_category_id)
    else:
        flashcards_qs = Flashcard.objects.none()

    # Convert QuerySet to list of dicts for JSON serialization
    flashcards = [
        {"question": f.question, "answer": f.answer}
        for f in flashcards_qs
    ]

    return render(request, 'flashcards/study.html', {
        'categories': categories,
        'flashcards': flashcards,
        'selected_category_id': selected_category_id or "",
    })
