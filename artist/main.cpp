#include <fcntl.h>
#include <errno.h>
#include "main.h"
#include "MyFrame.h"

class MyApp : public wxApp
{
    public:
        virtual bool OnInit();
};

IMPLEMENT_APP(MyApp)

bool MyApp::OnInit()
{
    wxInitAllImageHandlers();
    MyFrame *frame = new MyFrame();
    frame->Show(true);
    frame->Centre();
    return true;
}
