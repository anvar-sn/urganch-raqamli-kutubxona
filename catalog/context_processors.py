from .models import Book


def library_navigation(request):
    """Provide lightweight global navigation visibility flags."""
    return {
        'has_teacher_books': Book.objects.filter(
            approved=True, is_teacher_book=True
        ).exists(),
    }
