final EMAIL_RECIPIENTS_CSV="jakub.filak@sap.com"
final EMAIL_SUBJECT_PREFIX="DDIC: sapcli docker image "
final EMAIL_BODY="See ${env.BUILD_URL} for more details."

node ('factory') {

  emailext to:EMAIL_RECIPIENTS_CSV, subject:EMAIL_SUBJECT_PREFIX + "[STARTED]", body:EMAIL_BODY, mimeType: 'text/html'

  try {
    deleteDir()

    checkout scm

    withCredentials([usernamePassword(credentialsId: 'artifactory-user', passwordVariable: 'PASSWORD', usernameVariable: 'USERNAME')]) {

      sh '''
      set -o errexit

      docker login -u ${USERNAME} -p ${PASSWORD} dlm.int.repositories.cloud.sap

      set +o errexit

      echo "Build & release ..."
      make docker release-docker DOCKER=docker SKIP_LOCAL_COMMITS_CHECK=true
      result=$?

      echo "Clean up ..."
      docker rmi sapcli:latest
      docker rmi dlm.int.repositories.cloud.sap/automation/sapcli:latest

      exit $result
      '''
    }

    emailext to:EMAIL_RECIPIENTS_CSV, subject:EMAIL_SUBJECT_PREFIX + "[FINISHED]", body:EMAIL_BODY, mimeType: 'text/html'
  }
  catch (ex) {
    emailext to:EMAIL_RECIPIENTS_CSV, subject:EMAIL_SUBJECT_PREFIX + "[FAILED]", body:EMAIL_BODY, mimeType: 'text/html'
  }
}
