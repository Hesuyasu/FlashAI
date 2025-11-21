from datetime import timedelta
from django.utils import timezone
from .models import Flashcard, Category, PDFDocument
from django.shortcuts import render, get_object_or_404, redirect
from .forms import FlashcardForm, CategoryForm, PDFUploadForm
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

def study_flashcards(request):
    selected_category_id = request.GET.get('category')
    categories = Category.objects.all()
    if selected_category_id:
        flashcards_qs = Flashcard.objects.filter(category_id=selected_category_id)
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


''' @login_required
def flashcard_list(request):
    flashcards = Flashcard.objects.filter(user=request.user)
    return render(request, 'flashcards/flashcard_list.html', {'flashcards': flashcards})

@login_required
def flashcard_create(request):
    if request.method == 'POST':
        form = FlashcardForm(request.POST)
        if form.is_valid():
            flashcard = form.save(commit=False)
            flashcard.user = request.user
            flashcard.save()
            return redirect('flashcard_list')
    else:
        form = FlashcardForm()
    return render(request, 'flashcards/flashcard_form.html', {'form': form})

@login_required
def flashcard_update(request, pk):
    flashcard = get_object_or_404(Flashcard, pk=pk, user=request.user)
    form = FlashcardForm(request.POST or None, instance=flashcard)
    if form.is_valid():
        form.save()
        return redirect('flashcard_list')
    return render(request, 'flashcards/flashcard_form.html', {'form': form})

@login_required
def flashcard_delete(request, pk):
    flashcard = get_object_or_404(Flashcard, pk=pk, user=request.user)
    if request.method == 'POST':
        flashcard.delete()
        return redirect('flashcard_list')
    return render(request, 'flashcards/flashcard_confirm_delete.html', {'flashcard': flashcard})'''


def upload_pdf(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('upload_pdf')
    else:
        form = PDFUploadForm()

    pdfs = PDFDocument.objects.order_by('-uploaded_at')
    return render(request, 'upload_pdf.html', {
        'form': form,
        'pdf_list': pdfs,
    })


class HomePageView(TemplateView):
    template_name = "home.html"

def home(request):
    total_flashcards = Flashcard.objects.count()
    categories_count = Category.objects.count()
    new_this_week = Flashcard.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=7)
    ).count()
    return render(request, 'home.html', {
        'total_flashcards': total_flashcards,
        'categories_count': categories_count,
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

    return render(request, 'flashcards/flashcard_form.html', {'form': form})







#def collection_history(request):
#    flashcards = Flashcard.objects.order_by('-created_at')
#    return render(request, 'collection_history.html', {'flashcards': flashcards})


def flashcard_list(request):
    flashcards = Flashcard.objects.all()
    return render(request, 'flashcard_list.html', {'flashcards': flashcards})


def flashcard_update(request, pk):
    flashcard = get_object_or_404(Flashcard, pk=pk) # user=request.user 
    form = FlashcardForm(request.POST or None, instance=flashcard)
    if form.is_valid():
        form.save()
        return redirect('flashcard_list')
    return render(request, 'flashcards/flashcard_form.html', {'form': form})

def flashcard_delete(request, pk):
    flashcard = get_object_or_404(Flashcard, pk=pk) # user=request.user
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
    return render(request, "create_category.html", {"form": form})
