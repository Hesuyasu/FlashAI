from datetime import timedelta
from django.utils import timezone
from .models import Flashcard, Category, PDFDocument
from django.db.models import Q
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

@login_required(login_url='/account/login/')
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
            pdf_instance = form.save(commit=False)
            pdf_instance.user = request.user
            pdf_instance.save()
            category_name = request.POST.get('category') or 'Other'
            category_obj, _ = Category.objects.get_or_create(name=category_name, user=request.user)
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
                        category=category_obj,
                        user=request.user,
                        option_a=card.get('option_a', ''),
                        option_b=card.get('option_b', ''),
                        option_c=card.get('option_c', ''),
                        option_d=card.get('option_d', ''),
                        correct_option=card.get('correct_option', '')
                    )
            return redirect('flashcard_list')
    else:
        form = PDFUploadForm()

    pdfs = PDFDocument.objects.filter(user=request.user).order_by('-uploaded_at')
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
    """Dashboard view: provide counts and recent flashcards.

    Adds recent_flashcards list limited to last 6 items for display in base template.
    """
    flashcard_count = Flashcard.objects.filter(user=request.user).count()
    recent_flashcards = Flashcard.objects.filter(user=request.user).order_by('-created_at')[:6]
    return render(request, 'home.html', {
        'flashcard_count': flashcard_count,
        'recent_flashcards': recent_flashcards,
    })


@login_required(login_url='/account/login/')
def create_flashcard(request):
    if request.method == 'POST':
        form = FlashcardForm(request.POST)
        if form.is_valid():
            category_name = form.cleaned_data['category_name']
            category, created = Category.objects.get_or_create(name=category_name, user=request.user)
            flashcard = Flashcard(
                question=form.cleaned_data['question'],
                answer=form.cleaned_data['answer'],
                category=category,
                user=request.user,
                option_a=form.cleaned_data.get('option_a',''),
                option_b=form.cleaned_data.get('option_b',''),
                option_c=form.cleaned_data.get('option_c',''),
                option_d=form.cleaned_data.get('option_d',''),
                correct_option=form.cleaned_data.get('correct_option','')
            )
            flashcard.save()
            return redirect('flashcard_list')
    else:
        form = FlashcardForm()

    return render(request, 'create_flashcard.html', {'form': form})




#def collection_history(request):
#    flashcards = Flashcard.objects.order_by('-created_at')
#    return render(request, 'collection_history.html', {'flashcards': flashcards})


@login_required(login_url='/account/login/')
def flashcard_list(request):
    flashcards = Flashcard.objects.filter(user=request.user)
    return render(request, 'flashcard_list.html', {'flashcards': flashcards})


@login_required(login_url='/account/login/')
def flashcard_update(request, pk):
    flashcard = get_object_or_404(Flashcard, pk=pk, user=request.user)
    form = FlashcardForm(request.POST or None, instance=flashcard)
    if form.is_valid():
        obj = form.save(commit=False)
        category_name = request.POST.get('category_name')
        if category_name:
            category, _ = Category.objects.get_or_create(name=category_name, user=request.user)
            obj.category = category
        obj.save()
        return redirect('flashcard_list')
    return render(request, 'flashcards/flashcard_form.html', {'form': form})


@login_required(login_url='/account/login/')
def flashcard_delete(request, pk):
    flashcard = get_object_or_404(Flashcard, pk=pk, user=request.user)
    if request.method == 'POST':
        flashcard.delete()
        return redirect('flashcard_list')
    return render(request, 'flashcards/flashcard_confirm_delete.html', {'flashcard': flashcard})

@login_required(login_url='/account/login/')
def create_category(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            return redirect('create_flashcard')
    else:
        form = CategoryForm()
    categories = Category.objects.filter(user=request.user).order_by('name')
    return render(request, "create_category.html", {"form": form, "categories": categories})

@login_required(login_url='/account/login/')
def delete_category(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST':
        category.delete()
    return redirect('create_category')


def api_flashcard_count(request):
    count = Flashcard.objects.filter(user=request.user).count() if request.user.is_authenticated else 0
    return JsonResponse({'count': count})


@login_required(login_url='/account/login/')
def study_flashcards(request):
    selected_category_id = request.GET.get('category')
    categories = Category.objects.filter(
        Q(user=request.user) | Q(flashcard__user=request.user)
    ).distinct().order_by('name')
    if selected_category_id:
        flashcards_qs = Flashcard.objects.filter(
            category_id=selected_category_id, user=request.user)
    else:
        flashcards_qs = Flashcard.objects.none()

    flashcards = []
    for f in flashcards_qs:
        options = [f.option_a, f.option_b, f.option_c, f.option_d]
        options = [o for o in options if o]
        flashcards.append({
            "question": f.question,
            "answer": f.answer,
            "options": options,
            "correct": f.correct_option or ""
        })

    return render(request, 'flashcards/study.html', {
        'categories': categories,
        'flashcards': flashcards,
        'selected_category_id': selected_category_id or "",
    })
