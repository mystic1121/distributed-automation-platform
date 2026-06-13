pipeline {
  agent any
  environment {
    AWS_REGION  = 'ap-south-1'
    ACCOUNT     = '335651423113'
    ECR         = "${ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    BACKEND_ASG = 'kpi-backend-asg'
    // Cross-stage scratch dir for the worker rebake (builder id, baked sha, ami id).
    STATE_DIR   = "${WORKSPACE}/.rebake-state"
  }
  stages {

    // ===================== 1. Checkout Source =====================
    stage('Checkout Source') {
      steps {
        checkout scm
        script { env.TAG = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim() }
        echo "Deploying commit ${env.TAG}"
      }
    }

    // ===================== BACKEND =====================
    // build once → ECR → bump tag → refresh

    stage('Backend: Build Docker Image') {
      steps { sh 'bash ci/backend/build-image.sh' }
    }
    stage('Backend: Push Image to ECR') {
      steps { sh 'bash ci/backend/push-image.sh' }
    }
    stage('Backend: Update Image Tag') {
      steps { sh 'bash ci/backend/update-image-tag.sh' }
    }
    stage('Backend: Refresh ASG') {
      steps { sh 'bash ci/backend/refresh-asg.sh' }
    }

    // ===================== WORKER =====================
    // launch builder → fresh clone → verify sha → bake AMI → relink LT → refresh

    stage('Worker: Launch Builder') {
      steps { sh 'bash ci/worker/launch-builder.sh' }
    }
    stage('Worker: Fresh Clone Repository') {
      steps { sh 'bash ci/worker/provision.sh' }
    }
    stage('Worker: Verify Commit SHA') {
      steps { sh 'bash ci/worker/verify.sh' }
    }
    stage('Worker: Bake AMI') {
      steps { sh 'bash ci/worker/bake.sh' }
    }
    stage('Worker: Update Launch Template') {
      steps { sh 'bash ci/worker/update-launch-template.sh' }
    }
    stage('Worker: Refresh ASG') {
      steps { sh 'bash ci/worker/refresh-asg.sh' }
    }
  }
  post {
    // always tear down the temporary builder, whether the pipeline succeeded or failed at any stage.
    always {
      sh 'bash ci/worker/cleanup.sh'
    }
    success { echo "Deployed ${env.TAG}: backend image in ECR, worker AMI rebaked (verified == ${env.TAG}), both ASGs refreshing." }
    failure { echo "Deploy failed — check which stage; fleets only change after their stage succeeds. A worker-stage failure usually means the builder's HEAD did not match ${env.TAG} (git update didn't take)." }
  }
}
