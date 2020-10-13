
node ('factory') {

  deleteDir()

  checkout scm

  withCredentials([usernamePassword(credentialsId: 'artifactory-user', passwordVariable: 'PASSWORD', usernameVariable: 'USERNAME')]) {

    sh '''
    set -o errexit

    docker login -u ${USERNAME} -p ${PASSWORD} docker.wdf.sap.corp:51190

    set +o errexit

    echo "Build & release ..."
    make docker release-docker DOCKER=docker SKIP_LOCAL_COMMITS_CHECK=true
    result=$?

    echo "Clean up ..."
    docker rmi sapcli:latest
    docker rmi docker.wdf.sap.corp:51190/automation/sapcli:latest

    exit $result
    '''
  }
}
