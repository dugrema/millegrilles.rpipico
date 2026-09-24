pipeline {
    agent { label 'x86_64' }

    parameters {
        string(defaultValue: 'master', name: 'BRANCH')
        string(defaultValue: '2026.6', name: 'VERSION')
        string(defaultValue: 'jenkins-maple', name: 'CREDENTIALS_ID')
        string(defaultValue: 'ssh://git.maple.maceroc.com/git/millegrilles.rpipico.git', name: 'GIT_URL')
    }

    environment {
        VBUILD="${VERSION}.${BUILD_NUMBER}"
    }

    stages {
        stage('docker build x86_64') {
            steps {
                checkout scmGit(branches: [[name: params.BRANCH]], userRemoteConfigs: [[credentialsId: params.CREDENTIALS_ID, url: params.GIT_URL]])

                sh '''
                # Initialiser submodule micropython, oryx-embedded
                git submodule update --init micropython
                git submodule update --init --recursive oryx-embedded

                # Build submodules
                cd "micropython/"
                make -C mpy-cross
                make -C ports/rp2 BOARD=RPI_PICO_W submodules
                cd ..

                # Set build number dans le code
                echo "MILLEGRILLES_VERSION=const('${VBUILD}')" > millegrilles/python/millegrilles/version.py

                # Cleanup
                rm build/* || true

                # Build .mpy, firmware
                ./build.sh

                # Mettre version, compresser
                mv build/firmware.uf2 "build/millegrilles_${VBUILD}.uf2"
                xz -9e build/millegrilles_${VBUILD}.uf2
                '''

                archiveArtifacts artifacts: 'build/', followSymlinks: false
            }
        }
    }
}
