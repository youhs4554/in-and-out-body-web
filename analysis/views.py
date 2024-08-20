# analysis/views.py

import os
import pandas as pd
from django.shortcuts import render, redirect
from django.core.files.storage import default_storage
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import IntegrityError
from .models import UserInfo, GaitAnalysis, BodyTypeAnalysis
from .forms import UploadFileForm

def home(request):
    if request.user.is_authenticated:
        return redirect('upload_file')
    else:
        return redirect('login')

@login_required
def upload_file(request):
    users = []  # Initialize an empty list to hold user data

    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['file']
            file_path = default_storage.save('temp.xlsx', excel_file)
            full_path = os.path.join(settings.MEDIA_ROOT, 'temp.xlsx')

            # Read the Excel file
            df = pd.read_excel(full_path)
            
            for _, row in df.iterrows():
                try:
                    # Find or create the UserInfo
                    user_info, created = UserInfo.objects.update_or_create(
                        school=row['school'],
                        class_name=row['class'],
                        student_number=row['number'],
                        name=row['name'],
                        phone_number=row['phone_number'],
                    )

                    users.append(user_info)

                    # Create or update GaitAnalysis
                    gait_analysis, _ = GaitAnalysis.objects.update_or_create(
                        user=user_info,
                        defaults={
                            'speed': row.get('speed', 0),
                            'stride_length': row.get('stride_length', 0),
                            'cadence': row.get('cadence', 0)
                        }
                    )

                    # Create or update BodyTypeAnalysis
                    body_type_analysis, _ = BodyTypeAnalysis.objects.update_or_create(
                        user=user_info,
                        defaults={
                            'turtle_neck': row.get('turtle_neck', 'N/A'),
                            'shoulder_tilt': row.get('shoulder_tilt', 'N/A')
                        }
                    )
                except IntegrityError:
                    # Handle potential duplicate entry errors gracefully
                    pass

            # Cleanup
            default_storage.delete(file_path)

            return render(request, 'upload.html', {
                'form': form,
                'users': users
            })
    else:
        form = UploadFileForm()
    
    return render(request, 'upload.html', {'form': form})

@login_required
def report(request):
    grades = UserInfo.objects.values_list('class_name', flat=True).distinct()
    if request.method == 'POST':
        selected_grade = request.POST.get('grade')
        users = UserInfo.objects.filter(class_name=selected_grade)
    else:
        users = UserInfo.objects.none()
        selected_grade = None
    return render(request, 'report.html', {'grades': grades, 'users': users, 'selected_grade': selected_grade})

def policy(request):
    return render(request, 'policy.html')