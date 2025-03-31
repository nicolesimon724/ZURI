import os
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.conf import settings
from io import BytesIO
from .models import IssuedBook, Book
from django.shortcuts import render
from django.http import HttpResponseRedirect
from . import forms, models
from django.http import HttpResponseRedirect
from django.contrib.auth.models import Group
from django.contrib import auth
from django.contrib.auth.decorators import login_required, user_passes_test
from datetime import datetime, timedelta, date
from django.core.mail import send_mail
from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect
# from librarymanagement.settings import EMAIL_HOST_USER


def home_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('afterlogin')
    return render(request, 'library/index.html')

# for showing signup/login button for student


def studentclick_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('afterlogin')
    return render(request, 'library/studentclick.html')

# for showing signup/login button for teacher


def adminclick_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('afterlogin')
    return render(request, 'library/adminclick.html')


def adminsignup_view(request):
    form = forms.AdminSigupForm()
    if request.method == 'POST':
        form = forms.AdminSigupForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.set_password(user.password)
            user.save()

            my_admin_group = Group.objects.get_or_create(name='ADMIN')
            my_admin_group[0].user_set.add(user)

            return HttpResponseRedirect('adminlogin')
    return render(request, 'library/adminsignup.html', {'form': form})


def studentsignup_view(request):
    form1 = forms.StudentUserForm()
    form2 = forms.StudentExtraForm()
    mydict = {'form1': form1, 'form2': form2}
    if request.method == 'POST':
        form1 = forms.StudentUserForm(request.POST)
        form2 = forms.StudentExtraForm(request.POST)
        if form1.is_valid() and form2.is_valid():
            user = form1.save()
            user.set_password(user.password)
            user.save()
            f2 = form2.save(commit=False)
            f2.user = user
            user2 = f2.save()

            my_student_group = Group.objects.get_or_create(name='STUDENT')
            my_student_group[0].user_set.add(user)

        return HttpResponseRedirect('studentlogin')
    return render(request, 'library/studentsignup.html', context=mydict)


def is_admin(user):
    return user.groups.filter(name='ADMIN').exists()


def afterlogin_view(request):
    if is_admin(request.user):
        return render(request, 'library/adminafterlogin.html')
    else:
        return render(request, 'library/studentafterlogin.html')


@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def addbook_view(request):
    # now it is empty book form for sending to html
    form = forms.BookForm()
    if request.method == 'POST':
        # now this form have data from html
        form = forms.BookForm(request.POST)
        if form.is_valid():
            user = form.save()
            return render(request, 'library/bookadded.html')
    return render(request, 'library/addbook.html', {'form': form})


@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def viewbook_view(request):
    books = models.Book.objects.all()
    return render(request, 'library/viewbook.html', {'books': books})


@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def issuebook_view(request):
    form = forms.IssuedBookForm()
    if request.method == 'POST':
        # now this form have data from html
        form = forms.IssuedBookForm(request.POST)
        if form.is_valid():
            obj = models.IssuedBook()
            obj.enrollment = request.POST.get('enrollment2')
            obj.isbn = request.POST.get('isbn2')
            obj.save()
            return render(request, 'library/bookissued.html')
    return render(request, 'library/issuebook.html', {'form': form})


@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def viewissuedbook_view(request):
    issuedbooks = models.IssuedBook.objects.all()
    li = []
    for ib in issuedbooks:
        issdate = str(ib.issuedate.day)+'-' + \
            str(ib.issuedate.month)+'-'+str(ib.issuedate.year)
        expdate = str(ib.expirydate.day)+'-' + \
            str(ib.expirydate.month)+'-'+str(ib.expirydate.year)
        # fine calculation
        days = (date.today()-ib.issuedate)
        print(date.today())
        d = days.days
        fine = 0
        if d > 15:
            day = d-15
            fine = day*10

        books = list(models.Book.objects.filter(isbn=ib.isbn))
        students = list(models.StudentExtra.objects.filter(
            enrollment=ib.enrollment))
        i = 0
        for l in books:
            t = (students[i].get_name, students[i].enrollment,
                 books[i].name, books[i].author, issdate, expdate, fine)
            i = i+1
            li.append(t)

    return render(request, 'library/viewissuedbook.html', {'li': li})


@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def viewstudent_view(request):
    students = models.StudentExtra.objects.all()
    return render(request, 'library/viewstudent.html', {'students': students})


@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def viewanalytics_view(request):
    from django.db.models import Count
    # Most borrowed books - counts borrowing instances for each ISBN
    book_borrowing_data = IssuedBook.objects.values('isbn').annotate(
        borrow_count=Count('id')
    ).order_by('-borrow_count')

    # Add book name and other details to the results
    for item in book_borrowing_data:
        isbn = item['isbn']
        # Lookup the book details by isbn
        try:
            book = Book.objects.get(isbn=isbn)
            item['book__name'] = book.name
            item['book__author'] = book.author
            item['book__category'] = book.category
        except Book.DoesNotExist:
            item['book__name'] = f"Unknown ({isbn})"
            item['book__author'] = "Unknown"
            item['book__category'] = "Unknown"

    # Most popular authors
    author_borrowing_data = []
    authors_count = {}

    # Process issued books to count by author
    for issued_book in IssuedBook.objects.all():
        try:
            book = Book.objects.get(isbn=issued_book.isbn)
            if book.author in authors_count:
                authors_count[book.author] += 1
            else:
                authors_count[book.author] = 1
        except Book.DoesNotExist:
            pass

    # Convert to list format for template
    for author, count in authors_count.items():
        author_borrowing_data.append({
            'book__author': author,
            'borrow_count': count
        })

    # Sort by borrow count descending
    author_borrowing_data = sorted(
        author_borrowing_data,
        key=lambda x: x['borrow_count'],
        reverse=True
    )

    # Most popular categories - similar approach
    category_borrowing_data = []
    categories_count = {}

    for issued_book in IssuedBook.objects.all():
        try:
            book = Book.objects.get(isbn=issued_book.isbn)
            if book.category in categories_count:
                categories_count[book.category] += 1
            else:
                categories_count[book.category] = 1
        except Book.DoesNotExist:
            pass

    for category, count in categories_count.items():
        category_borrowing_data.append({
            'book__category': category,
            'borrow_count': count
        })

    category_borrowing_data = sorted(
        category_borrowing_data,
        key=lambda x: x['borrow_count'],
        reverse=True
    )

    context = {
        'book_borrowing_data': book_borrowing_data,
        'author_borrowing_data': author_borrowing_data,
        'category_borrowing_data': category_borrowing_data,
    }

    return render(request, 'library/viewanalytics.html', context)


def link_callback(uri, rel):
    """
    Convert HTML URIs to absolute system paths so xhtml2pdf can access those resources
    """
    # use short variable names
    static_url = settings.STATIC_URL
    static_root = settings.STATIC_ROOT
    media_url = settings.MEDIA_URL
    media_root = settings.MEDIA_ROOT

    # convert URIs to absolute system paths
    if uri.startswith(static_url):
        path = os.path.join(static_root, uri.replace(static_url, ""))
    elif uri.startswith(media_url):
        path = os.path.join(media_root, uri.replace(media_url, ""))
    else:
        return uri  # handle absolute uri (ie: http://some.tld/foo.png)

    # make sure that file exists
    if not os.path.isfile(path):
        raise Exception(
            'media URI must start with %s or %s' % (static_url, media_url)
        )
    return path


@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def download_analytics_pdf(request):
    # Reuse the same analytics data gathering logic from viewanalytics_view
    from django.db.models import Count

    # Most borrowed books
    book_borrowing_data = IssuedBook.objects.values('isbn').annotate(
        borrow_count=Count('id')
    ).order_by('-borrow_count')

    # Add book details
    for item in book_borrowing_data:
        isbn = item['isbn']
        try:
            book = Book.objects.get(isbn=isbn)
            item['book__name'] = book.name
            item['book__author'] = book.author
            item['book__category'] = book.category
        except Book.DoesNotExist:
            item['book__name'] = f"Unknown ({isbn})"
            item['book__author'] = "Unknown"
            item['book__category'] = "Unknown"

    # Most popular authors
    author_borrowing_data = []
    authors_count = {}

    for issued_book in IssuedBook.objects.all():
        try:
            book = Book.objects.get(isbn=issued_book.isbn)
            if book.author in authors_count:
                authors_count[book.author] += 1
            else:
                authors_count[book.author] = 1
        except Book.DoesNotExist:
            pass

    for author, count in authors_count.items():
        author_borrowing_data.append({
            'book__author': author,
            'borrow_count': count
        })

    author_borrowing_data = sorted(
        author_borrowing_data,
        key=lambda x: x['borrow_count'],
        reverse=True
    )

    # Most popular categories
    category_borrowing_data = []
    categories_count = {}

    for issued_book in IssuedBook.objects.all():
        try:
            book = Book.objects.get(isbn=issued_book.isbn)
            if book.category in categories_count:
                categories_count[book.category] += 1
            else:
                categories_count[book.category] = 1
        except Book.DoesNotExist:
            pass

    for category, count in categories_count.items():
        category_borrowing_data.append({
            'book__category': category,
            'borrow_count': count
        })

    category_borrowing_data = sorted(
        category_borrowing_data,
        key=lambda x: x['borrow_count'],
        reverse=True
    )

    # Current date for the report
    today = date.today().strftime("%B %d, %Y")

    # Prepare context for template
    context = {
        'book_borrowing_data': book_borrowing_data,
        'author_borrowing_data': author_borrowing_data,
        'category_borrowing_data': category_borrowing_data,
        'today': today,
        'title': 'Library Analytics Report'
    }

    # Get the template
    template = get_template('library/analytics_pdf.html')

    # Render the template with context
    html = template.render(context)

    # Create a PDF response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="library_analytics_{date.today().strftime("%Y%m%d")}.pdf"'

    # Generate PDF
    pisa_status = pisa.CreatePDF(
        html, dest=response, link_callback=link_callback)

    # Return response
    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)

    return response


@login_required(login_url='studentlogin')
def viewissuedbookbystudent(request):
    student = models.StudentExtra.objects.filter(user_id=request.user.id)
    issuedbook = models.IssuedBook.objects.filter(
        enrollment=student[0].enrollment)

    li1 = []

    li2 = []
    for ib in issuedbook:
        books = models.Book.objects.filter(isbn=ib.isbn)
        for book in books:
            t = (request.user, student[0].enrollment,
                 student[0].branch, book.name, book.author)
            li1.append(t)
        issdate = str(ib.issuedate.day)+'-' + \
            str(ib.issuedate.month)+'-'+str(ib.issuedate.year)
        expdate = str(ib.expirydate.day)+'-' + \
            str(ib.expirydate.month)+'-'+str(ib.expirydate.year)
        # fine calculation
        days = (date.today()-ib.issuedate)
        print(date.today())
        d = days.days
        fine = 0
        if d > 15:
            day = d-15
            fine = day*10
        t = (issdate, expdate, fine)
        li2.append(t)

    return render(request, 'library/viewissuedbookbystudent.html', {'li1': li1, 'li2': li2})


def aboutus_view(request):
    return render(request, 'library/aboutus.html')


def contactus_view(request):
    sub = forms.ContactusForm()
    if request.method == 'POST':
        sub = forms.ContactusForm(request.POST)
        if sub.is_valid():
            email = sub.cleaned_data['Email']
            name = sub.cleaned_data['Name']
            message = sub.cleaned_data['Message']
            send_mail(str(name)+' || '+str(email), message, EMAIL_HOST_USER,
                      ['wapka1503@gmail.com'], fail_silently=False)
            return render(request, 'library/contactussuccess.html')
    return render(request, 'library/contactus.html', {'form': sub})


def custom_logout_view(request):
    logout(request)
    messages.success(request, "You have been successfully logged out!")
    return redirect('/')
