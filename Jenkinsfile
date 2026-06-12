pipeline {
  agent any
  environment {
    AWS_REGION  = 'ap-south-1'
    ACCOUNT     = '335651423113'
    ECR         = "${ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    BACKEND_ASG = 'kpi-backend-asg'
  }
  stages {
    stage('Checkout') {
      steps {
        checkout scm
        script { env.TAG = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim() }
        echo "Deploying commit ${env.TAG}"
      }
    }

    // ---------- BACKEND: build once → ECR → bump tag → refresh ----------
    stage('Backend: build & push image') {
      steps {
        sh '''
          aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR
          docker build -t $ECR/kpi-backend:$TAG kpi-automation-backend
          docker push $ECR/kpi-backend:$TAG
          aws ssm put-parameter --name /kpi/backend/image-tag --type String --overwrite --value $TAG --region $AWS_REGION
        '''
      }
    }
    stage('Backend: roll fleet') {
      steps {
        sh '''
          aws autoscaling start-instance-refresh --auto-scaling-group-name $BACKEND_ASG \
            --preferences '{"MinHealthyPercentage":50,"InstanceWarmup":120}' --region $AWS_REGION
        '''
      }
    }

    // ---------- WORKER: scripted AMI rebake → relink launch template → refresh ----------
    stage('Worker: rebake AMI & roll fleet') {
      steps {
        sh 'bash ci/rebake-worker-ami.sh $TAG'
      }
    }
  }
  post {
    success { echo "Deployed ${env.TAG}: backend image in ECR, worker AMI rebaked (verified == ${env.TAG}), both ASGs refreshing." }
    failure { echo "Deploy failed — check which stage; fleets only change after their stage succeeds. A worker-stage failure usually means the builder's HEAD did not match ${env.TAG} (git update didn't take)." }
  }
}
